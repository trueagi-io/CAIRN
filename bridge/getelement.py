"""Local copy for PeTTa py-call (AFImportanceDiffusionAgent). Upstream lives in metta-attention."""


def getTopK(l, k):
    if k <= 0:
        return []
    return sorted(l, reverse=True)[:k]


def getK(l, k):
    if k <= 0:
        return []
    return l[:k]
