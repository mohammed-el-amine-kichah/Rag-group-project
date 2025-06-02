import re, unicodedata

_AR_RE = re.compile(r"[ء-ي]")

def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text)                 # collapse whitespace
    text = re.sub(r"[|•◦▪·■□◆]", " ", text)          # remove decorative bullets
    return re.sub(r" {2,}", " ", text).strip()

def is_quality(text: str, min_len=30, min_ar_ratio=0.3) -> bool:
    if len(text) < min_len:
        return False
    return (len(_AR_RE.findall(text)) / len(text)) >= min_ar_ratio

