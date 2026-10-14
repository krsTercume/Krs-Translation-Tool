"""Format readers. make_doc() picks the right one."""
from .text_tra import Doc
from .ags_dta import DtaDoc, CrmDoc
from .ags_bintra import BinTraDoc
from .renpy import RenpyDoc



def make_doc(path):
    with open(path, "rb") as f:
        head = f.read(32)
    if head.startswith(b"Adventure Creator Game File"):
        return DtaDoc(path)
    if head.startswith(b"AGSTranslation\0"):
        return BinTraDoc(path)
    if path.lower().endswith(".crm"):
        return CrmDoc(path)
    if path.lower().endswith(".rpy"):
        return RenpyDoc(path)
    return Doc(path)

