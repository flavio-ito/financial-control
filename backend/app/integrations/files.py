"""Bounded CSV and OFX bank-statement readers; no uploaded file is stored."""
from datetime import datetime
import csv
import hashlib
import io
import re
import unicodedata

from app.domain.calculations import DomainValidationError
from app.integrations.contracts import Transaction, minor

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10000


def decode_with_encoding(raw):
    if not raw or len(raw) > MAX_FILE_BYTES or b"\x00" in raw:
        raise DomainValidationError("Arquivo vazio, binário ou maior que 5 MB.")
    try:
        return raw.decode("utf-8-sig"), "UTF-8"
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="strict"), "Windows-1252"


def decode(raw):
    return decode_with_encoding(raw)[0]


def normalized_header(value):
    value = unicodedata.normalize("NFKD", value.strip().casefold())
    return " ".join("".join(char for char in value if not unicodedata.combining(char)).replace("_", " ").split())


HEADER_ALIASES = {
    "date": {"data", "date", "data da transacao", "transaction date", "posted date", "data lancamento"},
    "description": {"descricao", "description", "title", "memo", "historico", "estabelecimento"},
    "amount": {"valor", "amount", "value", "valor da transacao", "valor lancamento"},
    "id": {"id", "identificador", "transaction id", "fitid", "id da transacao", "id da operacao"},
}


def csv_structure(text):
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=";,\t")
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        headers = reader.fieldnames or []
        if not headers or len(headers) != len(set(headers)):
            raise DomainValidationError("CSV sem cabeçalho válido ou com colunas repetidas.")
        rows = []
        for index, row in enumerate(reader, 1):
            if index > MAX_ROWS or None in row:
                raise DomainValidationError("CSV excede 10 mil linhas ou contém colunas inconsistentes.")
            rows.append(row)
        return dialect, headers, rows
    except (csv.Error, TypeError, AttributeError) as error:
        if isinstance(error, DomainValidationError):
            raise
        raise DomainValidationError("CSV inválido; confira separadores e cabeçalho.") from None


def _success_rate(rows, header, parser):
    sample = rows[:50]
    if not sample:
        return 0.0
    valid = 0
    for row in sample:
        try:
            if row.get(header, "").strip():
                parser(row[header])
                valid += 1
        except (DomainValidationError, ValueError, TypeError):
            pass
    return valid / len(sample)


def analyze_csv(raw, target_kind=None):
    """Infer a conservative mapping. Ambiguous fields remain empty for manual selection."""
    try:
        text, encoding = decode_with_encoding(raw)
    except UnicodeError:
        raise DomainValidationError("Codificação não suportada. Exporte como UTF-8 ou Windows-1252.") from None
    dialect, headers, rows = csv_structure(text)
    normalized = {header: normalized_header(header) for header in headers}
    mapping, confidence = {}, {}
    used = set()
    for field in ("date", "description", "amount", "id"):
        matches = [header for header in headers if normalized[header] in HEADER_ALIASES[field] and header not in used]
        if len(matches) == 1:
            mapping[field], confidence[field] = matches[0], 1.0
            used.add(matches[0])

    validators = {"date": br_date, "amount": br_amount}
    for field, parser in validators.items():
        if field in mapping:
            continue
        rates = sorted(((_success_rate(rows, header, parser), header) for header in headers if header not in used), reverse=True)
        if rates and rates[0][0] >= .9 and (len(rates) == 1 or rates[0][0] > rates[1][0]):
            confidence[field], mapping[field] = round(rates[0][0], 2), rates[0][1]
            used.add(rates[0][1])

    if "description" not in mapping:
        choices = []
        for header in headers:
            if header in used:
                continue
            values = [row.get(header, "").strip() for row in rows[:50]]
            score = sum(bool(value) and not re.fullmatch(r"[+-]?[\d., ]+", value) for value in values) / max(len(values), 1)
            choices.append((score, header))
        choices.sort(reverse=True)
        if choices and choices[0][0] >= .8 and (len(choices) == 1 or choices[0][0] > choices[1][0]):
            confidence["description"], mapping["description"] = round(choices[0][0], 2), choices[0][1]

    normalized_set = set(normalized.values())
    preset = "nubank_card" if {"date", "title", "amount"}.issubset(normalized_set) else None
    invert_signs = bool(preset == "nubank_card" and target_kind == "card")
    warnings = []
    missing = [field for field in ("date", "description", "amount") if not mapping.get(field)]
    if missing:
        warnings.append("Não foi possível identificar todas as colunas obrigatórias. Ajuste o mapeamento manualmente.")
    if not mapping.get("id"):
        warnings.append("Sem identificador estável: reimportar o mesmo arquivo é seguro, mas extratos sobrepostos exigem revisão.")
    if preset == "nubank_card" and target_kind == "card":
        warnings.append("Formato de fatura Nubank reconhecido: compras positivas serão invertidas para despesas na prévia.")
    elif preset == "nubank_card":
        warnings.append("Formato semelhante a fatura Nubank. Selecione um cartão para aplicar a convenção de sinais esperada.")
    return {"headers": headers, "mapping": {field: mapping.get(field, "") for field in ("date", "description", "amount", "id")},
            "confidence": confidence, "encoding": encoding,
            "delimiter": {";": "ponto e vírgula", ",": "vírgula", "\t": "tabulação"}.get(dialect.delimiter, dialect.delimiter),
            "preset": preset, "invert_signs": invert_signs, "warnings": warnings, "row_count": len(rows)}


def br_amount(value):
    text = value.strip().replace("R$", "").replace(" ", "").replace("\u00a0", "")
    if "," in text:
        if not re.fullmatch(r"[+-]?(?:\d+|\d{1,3}(?:\.\d{3})+),\d{1,2}", text):
            raise DomainValidationError("Valor brasileiro inválido no CSV.")
        text = text.replace(".", "").replace(",", ".")
    elif not re.fullmatch(r"[+-]?\d+(?:\.\d{1,2})?", text):
        raise DomainValidationError("Valor inválido no CSV.")
    return minor(text)


def br_date(value):
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            pass
    raise DomainValidationError("Data inválida; use dd/mm/aaaa ou aaaa-mm-dd.")


def parse_csv(text, digest, mapping=None, invert_signs=False):
    mapping = mapping or {"date": "data", "description": "descricao", "amount": "valor", "id": "id"}
    try:
        _dialect, headers, source_rows = csv_structure(text)
        required = [mapping.get(k) for k in ("date", "description", "amount")]
        if (any(value not in headers for value in required) or len(set(required)) != 3
                or (mapping.get("id") and mapping["id"] in required)):
            raise DomainValidationError("Mapeie as colunas de data, descrição e valor do CSV (nomes exatos do cabeçalho).")
        results = []
        for index, row in enumerate(source_rows, 1):
            external = row.get(mapping.get("id", ""))
            external = "id:" + external.strip() if external and external.strip() else "file:" + digest + ":" + str(index)
            amount = br_amount(row[mapping["amount"]])
            results.append(Transaction(external, br_date(row[mapping["date"]]), row[mapping["description"]].strip(), -amount if invert_signs else amount))
        return results
    except (csv.Error, TypeError, KeyError, AttributeError, ValueError) as error:
        if isinstance(error, DomainValidationError):
            raise
        raise DomainValidationError("CSV inválido; confira separadores, cabeçalho e valores.") from None


def parse_ofx(text, digest):
    # Deliberately narrow SGML/XML OFX subset. Never evaluate XML entities or DTDs.
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper() or "<OFX>" not in text.upper():
        raise DomainValidationError("OFX inválido ou contém declarações não suportadas.")
    if len(re.findall(r"<STMTRS>|<CCSTMTRS>", text, re.I)) != 1:
        raise DomainValidationError("OFX deve conter exatamente um extrato de conta ou cartão.")

    def field(block, name, required=True):
        match = re.search(r"<" + name + r">\s*([^<\r\n]+)", block, re.I)
        if not match and required:
            raise DomainValidationError("Campo obrigatório ausente no OFX: " + name)
        return match.group(1).strip() if match else None

    currency = field(text, "CURDEF")
    scope = "|".join(filter(None, (field(text, "BANKID", False), field(text, "ACCTID"))))
    scope = hashlib.sha256(scope.encode()).hexdigest()[:24]
    blocks = re.findall(r"<STMTTRN>(.*?)</STMTTRN>", text, re.S | re.I)
    if not blocks or len(blocks) > MAX_ROWS or len(blocks) != len(re.findall(r"<STMTTRN>", text, re.I)):
        raise DomainValidationError("OFX sem transações válidas ou excede 10 mil linhas.")
    results = []
    for index, block in enumerate(blocks, 1):
        try:
            transaction_date = datetime.strptime(field(block, "DTPOSTED")[:8], "%Y%m%d").date()
            fitid = field(block, "FITID", False)
            external = "fit:" + scope + ":" + fitid if fitid else "file:" + digest + ":" + str(index)
            results.append(Transaction(external, transaction_date,
                field(block, "MEMO", False) or field(block, "NAME"), minor(field(block, "TRNAMT")), currency))
        except (ValueError, TypeError):
            raise DomainValidationError("Data ou valor OFX inválido.") from None
    return results


def parse_file(raw, format, mapping=None, invert_signs=False):
    try:
        text = decode(raw)
    except UnicodeError:
        raise DomainValidationError("Codificação não suportada. Exporte como UTF-8 ou Windows-1252.") from None
    digest = hashlib.sha256(raw).hexdigest()
    if format == "csv":
        rows = parse_csv(text, digest, mapping, invert_signs)
    elif format == "ofx":
        rows = parse_ofx(text, digest)
    else:
        raise DomainValidationError("Formato deve ser CSV ou OFX.")
    if not rows:
        raise DomainValidationError("Arquivo não contém transações.")
    ids = [row.external_id for row in rows]
    if len(ids) != len(set(ids)):
        raise DomainValidationError("Arquivo contém identificadores repetidos; revise antes de importar.")
    return digest, rows


def detect_statement_kind(raw, format, analysis, rows):
    """Return account/card only when the document provides strong evidence."""
    text = decode(raw)
    if format == "ofx":
        upper = text.upper()
        if "<CCSTMTRS>" in upper or "<CREDITCARDMSGSRSV1>" in upper:
            return "card"
        if "<STMTRS>" in upper or "<BANKMSGSRSV1>" in upper:
            return "account"
        return None
    if analysis and analysis.get("preset") == "nubank_card":
        return "card"
    descriptions = " ".join(normalized_header(row.description) for row in rows[:200])
    account_patterns = (
        r"\btransferencia pix\b", r"\bpix enviado\b", r"\bpix recebido\b",
        r"\bted enviada\b", r"\bted recebida\b", r"\btransferencia recebida\b",
    )
    return "account" if any(re.search(pattern, descriptions) for pattern in account_patterns) else None
