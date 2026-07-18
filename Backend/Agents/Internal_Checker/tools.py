from datetime import datetime, date
from rapidfuzz import fuzz


# ── issue helper ──

def make_issue(doc_type, field, kind, message):
    """Build one issue in the standard shape."""
    return {
        "doc_type": doc_type,
        "field": field,
        "kind": kind,
        "message": message,
        "citation": None,
    }


# ── gate ──

def validate_lc_terms(lc_terms, schema):
    """Check LC has all gate_requirements and isn't expired.
    Returns (issues, lc_ok)."""
    issues = []
    required = schema.get("gate_requirements", [])

    for field in required:
        val = lc_terms.get(field)
        if val is None or val == "":
            issues.append(make_issue(
                "lc_terms", field, "lc_terms_incomplete",
                f"Required LC field '{field}' is missing or empty"
            ))

    if issues:
        return issues, False

    # all fields present — check expiry
    expiry = lc_terms.get("expiry_date")
    if expiry:
        exp_date = _parse_date(expiry)
        if exp_date is None:
            issues.append(make_issue(
                "lc_terms", "expiry_date", "date_invalid",
                f"Cannot parse expiry_date: {expiry}"
            ))
            return issues, False
        if exp_date < date.today():
            issues.append(make_issue(
                "lc_terms", "expiry_date", "lc_expired",
                f"LC expired on {expiry}"
            ))
            return issues, False

    return issues, True


# ── pass a: required documents ──

def check_required_documents(parsed_docs, lc_terms):
    """Check all docs the LC demands are present and readable."""
    issues = []
    required = lc_terms.get("required_documents", [])

    # handle case where LLM returned comma string instead of list
    if isinstance(required, str):
        required = [r.strip() for r in required.split(",") if r.strip()]

    for doc_type in required:
        if doc_type not in parsed_docs:
            issues.append(make_issue(
                doc_type, None, "missing_doc",
                f"Required document '{doc_type}' was not provided"
            ))
        elif parsed_docs[doc_type].get("parse_failed"):
            issues.append(make_issue(
                doc_type, None, "unreadable",
                f"Document '{doc_type}' could not be parsed"
            ))

    return issues


# ── pass a: completeness ──

def check_completeness(parsed_docs, schema):
    """For each doc, check required fields aren't null."""
    issues = []
    fields = schema.get("fields", [])

    for f in fields:
        if not f.get("required"):
            continue
        for doc_type in f.get("appears_in", []):
            doc = parsed_docs.get(doc_type)
            if doc is None or doc.get("parse_failed"):
                continue
            val = doc.get(f["field"])
            if val is None or val == "":
                issues.append(make_issue(
                    doc_type, f["field"], "missing_field",
                    f"Required field '{f['field']}' is empty on {doc_type}"
                ))

    return issues


# ── pass a: date checks ──

def check_dates(parsed_docs, lc_terms, schema):
    """Evaluate date_rules from schema with plain datetime math."""
    issues = []
    date_rules = schema.get("date_rules", [])

    for rule in date_rules:
        rule_type = rule.get("rule")

        if rule_type == "not_in_past":
            issues += _check_not_in_past(rule, parsed_docs, lc_terms)
        elif "before" in rule and "after" in rule:
            issues += _check_before_after(rule, parsed_docs, lc_terms)
        elif "within_days" in rule:
            issues += _check_within_days(rule, parsed_docs, lc_terms)

    return issues


def _check_not_in_past(rule, parsed_docs, lc_terms):
    """Date must not be in the past."""
    issues = []
    doc_type = rule.get("doc_type", "lc_terms")
    field = rule["field"]
    val = _get_field_value(parsed_docs, lc_terms, doc_type, field)
    if val is None:
        return issues

    d = _parse_date(val)
    if d is None:
        issues.append(make_issue(doc_type, field, "date_invalid",
            f"Cannot parse date '{val}' for {field} on {doc_type}"))
        return issues

    if d < date.today():
        issues.append(make_issue(doc_type, field, "date_rule_violated",
            f"{field} on {doc_type} is in the past ({val})"))

    return issues


def _check_before_after(rule, parsed_docs, lc_terms):
    """Field A must be on or before field B."""
    issues = []
    before_doc = rule.get("before_doc", "lc_terms")
    after_doc = rule.get("after_doc", "lc_terms")
    before_field = rule["before"]
    after_field = rule["after"]

    val_b = _get_field_value(parsed_docs, lc_terms, before_doc, before_field)
    val_a = _get_field_value(parsed_docs, lc_terms, after_doc, after_field)
    if val_b is None or val_a is None:
        return issues

    d_b = _parse_date(val_b)
    d_a = _parse_date(val_a)

    if d_b is None:
        issues.append(make_issue(before_doc, before_field, "date_invalid",
            f"Cannot parse date '{val_b}' for {before_field}"))
        return issues
    if d_a is None:
        issues.append(make_issue(after_doc, after_field, "date_invalid",
            f"Cannot parse date '{val_a}' for {after_field}"))
        return issues

    if d_b > d_a:
        article = rule.get("article", "")
        msg = f"{before_field} ({val_b}) must be on or before {after_field} ({val_a})"
        if article:
            msg += f" per {article}"
        issues.append(make_issue(before_doc, before_field, "date_rule_violated", msg))

    return issues


def _check_within_days(rule, parsed_docs, lc_terms):
    """Field A must be within N days of field B."""
    issues = []
    doc_type = rule.get("doc_type", "lc_terms")
    of_doc = rule.get("of_doc", "lc_terms")
    field = rule["field"]
    of_field = rule["of"]
    max_days = rule["within_days"]

    val = _get_field_value(parsed_docs, lc_terms, doc_type, field)
    val_of = _get_field_value(parsed_docs, lc_terms, of_doc, of_field)
    if val is None or val_of is None:
        return issues

    d = _parse_date(val)
    d_of = _parse_date(val_of)

    if d is None:
        issues.append(make_issue(doc_type, field, "date_invalid",
            f"Cannot parse date '{val}' for {field}"))
        return issues
    if d_of is None:
        issues.append(make_issue(of_doc, of_field, "date_invalid",
            f"Cannot parse date '{val_of}' for {of_field}"))
        return issues

    diff = abs((d - d_of).days)
    if diff > max_days:
        article = rule.get("article", "")
        msg = f"{field} ({val}) must be within {max_days} days of {of_field} ({val_of}), got {diff} days"
        if article:
            msg += f" per {article}"
        issues.append(make_issue(doc_type, field, "date_rule_violated", msg))

    return issues


# ── pass b: individual comparators ──

def compare_exact(val_a, val_b):
    """True if both values match after trimming."""
    return str(val_a).strip() == str(val_b).strip()


def compare_numeric(val_a, val_b, tolerance=0.0):
    """True if within tolerance. None if not numeric."""
    try:
        num_a = float(val_a)
        num_b = float(val_b)
    except (ValueError, TypeError):
        return None
    return abs(num_a - num_b) <= tolerance


def compare_date(val_a, val_b):
    """True if same date. None if either can't parse."""
    d_a = _parse_date(val_a)
    d_b = _parse_date(val_b)
    if d_a is None or d_b is None:
        return None
    return d_a == d_b


def fuzzy_score(str_a, str_b, high=92, low=40):
    """Score two strings with rapidfuzz. Returns score and band."""
    score = fuzz.token_sort_ratio(str(str_a), str(str_b))
    if score >= high:
        band = "match"
    elif score < low:
        band = "mismatch"
    else:
        band = "ambiguous"
    return {"score": score, "band": band}


# ── pass b: shared comparison dispatcher ──

def _compare_field(f, field_name, val_a, val_b, dt_a, dt_b):
    """Run the right comparator for one field pair.
    Returns (issue_or_None, ambiguous_pair_or_None)."""
    compare = f["compare"]
    issue = None
    pair = None

    if compare == "exact":
        if not compare_exact(val_a, val_b):
            issue = make_issue(
                dt_b, field_name, "exact_mismatch",
                f"{field_name} differs: '{val_a}' ({dt_a}) vs '{val_b}' ({dt_b})"
            )

    elif compare == "numeric_tolerance":
        tol = f.get("tolerance", 0.0)
        result = compare_numeric(val_a, val_b, tol)
        if result is None:
            issue = make_issue(
                dt_b, field_name, "numeric_mismatch",
                f"{field_name} not numeric: '{val_a}' ({dt_a}) vs '{val_b}' ({dt_b})"
            )
        elif not result:
            issue = make_issue(
                dt_b, field_name, "numeric_mismatch",
                f"{field_name} mismatch: {val_a} ({dt_a}) vs {val_b} ({dt_b}), tolerance {tol}"
            )

    elif compare == "date":
        result = compare_date(val_a, val_b)
        if result is not None and not result:
            issue = make_issue(
                dt_b, field_name, "date_mismatch",
                f"{field_name} date mismatch: {val_a} ({dt_a}) vs {val_b} ({dt_b})"
            )

    elif compare == "fuzzy":
        high = f.get("fuzzy_high", 92)
        low = f.get("fuzzy_low", 40)
        result = fuzzy_score(val_a, val_b, high, low)

        if result["band"] == "mismatch":
            issue = make_issue(
                dt_b, field_name, "fuzzy_mismatch",
                f"{field_name} fuzzy mismatch ({result['score']:.1f}): "
                f"'{val_a}' ({dt_a}) vs '{val_b}' ({dt_b})"
            )
        elif result["band"] == "ambiguous":
            pair = {
                "field": field_name,
                "doc_a": dt_a,
                "doc_b": dt_b,
                "val_a": str(val_a),
                "val_b": str(val_b),
                "score": result["score"],
            }

    return issue, pair


# ── pass b: consistency (7 docs vs each other) ──

def run_consistency_checks(parsed_docs, schema):
    """Compare supporting docs against each other for internal consistency.
    e.g. does invoice quantity match packing list quantity?"""
    issues = []
    ambiguous = []
    fields = schema.get("fields", [])

    for f in fields:
        compare = f.get("compare")
        appears_in = f.get("appears_in", [])
        if not compare or len(appears_in) < 2:
            continue

        field_name = f["field"]

        # collect values from supporting docs only, skip lc_terms
        values = {}
        for doc_type in appears_in:
            if doc_type == "lc_terms":
                continue
            doc = parsed_docs.get(doc_type)
            if doc is None or doc.get("parse_failed"):
                continue
            val = doc.get(field_name)
            if val is not None and val != "":
                values[doc_type] = val

        # need at least 2 supporting docs to compare
        doc_types = list(values.keys())
        if len(doc_types) < 2:
            continue

        # compare every pair
        for i in range(len(doc_types)):
            for j in range(i + 1, len(doc_types)):
                issue, pair = _compare_field(
                    f, field_name,
                    values[doc_types[i]], values[doc_types[j]],
                    doc_types[i], doc_types[j]
                )
                if issue:
                    issues.append(issue)
                if pair:
                    ambiguous.append(pair)

    return issues, ambiguous


# ── pass b: compliance (7 docs vs LC) ──

def run_compliance_checks(parsed_docs, lc_terms, schema):
    """Compare each supporting doc against the LC terms sheet.
    e.g. does invoice amount match LC amount?"""
    issues = []
    ambiguous = []
    fields = schema.get("fields", [])

    for f in fields:
        compare = f.get("compare")
        appears_in = f.get("appears_in", [])
        if not compare or "lc_terms" not in appears_in:
            continue

        field_name = f["field"]
        lc_val = lc_terms.get(field_name)
        if lc_val is None or lc_val == "":
            continue

        # compare each supporting doc against the LC value
        for doc_type in appears_in:
            if doc_type == "lc_terms":
                continue
            doc = parsed_docs.get(doc_type)
            if doc is None or doc.get("parse_failed"):
                continue
            val = doc.get(field_name)
            if val is None or val == "":
                continue

            issue, pair = _compare_field(
                f, field_name, lc_val, val, "lc_terms", doc_type
            )
            if issue:
                issues.append(issue)
            if pair:
                ambiguous.append(pair)

    return issues, ambiguous


# ── optional rag citation ──

def attach_citations(issues, query_fn=None):
    """Stamp UCP/ISBP article ref onto each issue via RAG retrieval.
    If query_fn is None, returns issues unchanged."""
    if query_fn is None:
        return issues

    for issue in issues:
        parts = []
        doc_type = issue.get("doc_type")
        if doc_type:
            parts.append(doc_type)
        if issue.get("field"):
            parts.append(issue["field"])
        parts.append(issue.get("kind", ""))
        query_text = " ".join(parts)

        corpus = None
        if doc_type in ["invoice", "bill_of_lading", "insurance_certificate"]:
            corpus = "ucp"
        elif doc_type in ["packing_list", "certificate_of_origin", "inspection_certificate"]:
            corpus = "isbp"

        try:
            results = query_fn(query_text, k=1, corpus=corpus)
            if results and len(results) > 0:
                issue["citation"] = results[0].get("ref")
        except Exception:
            pass

    return issues



# ── internal helpers ──

def _parse_date(val):
    """Parse a value into a date object. Returns None on failure."""
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                continue
    return None


def _get_field_value(parsed_docs, lc_terms, doc_type, field):
    """Get a field value from the right doc."""
    if doc_type == "lc_terms":
        return lc_terms.get(field)
    doc = parsed_docs.get(doc_type)
    if doc and not doc.get("parse_failed"):
        return doc.get(field)
    return None