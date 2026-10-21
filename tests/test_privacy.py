import pandas as pd
from dataco.ingestion import normalize
from dataco.quality import audit


def test_identity_columns_never_enter_model(raw_rows):
    secret = "PRIVATE_SENTINEL@example.invalid"
    raw = pd.DataFrame([raw_rows({"Customer Email":secret,"Customer Fname":secret,
                                  "Customer Password":secret,"Customer Street":secret,
                                  "Latitude":secret,"Longitude":secret})])
    d = normalize(raw)
    report, issues, _ = audit(raw, d)
    assert secret not in d.to_csv(index=False)
    assert secret not in issues.to_csv(index=False)
    assert not any("email" in c or "password" in c or "street" in c for c in d.columns)


def test_malformed_numeric_value_is_redacted_in_issue(raw_rows):
    secret = "PRIVATE_SENTINEL@example.invalid"
    raw = pd.DataFrame([raw_rows({"Days for shipping (real)":secret})])
    _, issues, _ = audit(raw, normalize(raw))
    assert secret not in issues.to_csv(index=False)
    assert "[REDACTED]" in issues.to_csv(index=False)

