import Config
import struct
import sysv_ipc

NEXT_POS = 0
HASHHEAD_POS = NEXT_POS + Config.USHM_SIZE * 4
NUMBER_POS = HASHHEAD_POS + (Config.UTMP_HASHSIZE + 1) * 4
LISTHEAD_POS = NUMBER_POS + 4
LISTPREV_POS = LISTHEAD_POS + 4
LISTNEXT_POS = LISTPREV_POS + 4 * Config.USHM_SIZE
UPTIME_POS = LISTNEXT_POS + 4 * Config.USHM_SIZE

class UtmpHead:
    utmphead = None

    @staticmethod
    def GetInt(pos, idx = 0):
        return struct.unpack('=i', UtmpHead.utmphead.read(4, pos + idx * 4))[0]

    @staticmethod
    def SetInt(pos, idx, val):
        UtmpHead.utmphead.write(struct.pack('=i', val), pos + idx * 4)

    @staticmethod
    def GetHashHead(hash):
        return UtmpHead.GetInt(HASHHEAD_POS, hash)

    @staticmethod
    def SetHashHead(hash, val):
        return UtmpHead.SetInt(HASHHEAD_POS, hash, val)

    @staticmethod
    def GetListHead():
        return UtmpHead.GetInt(LISTHEAD_POS)

    @staticmethod
    def SetListHead(head):
        return UtmpHead.SetInt(LISTHEAD_POS, 0, val)

    @staticmethod
    def GetListNext(pos):
        return UtmpHead.GetInt(LISTNEXT_POS, pos)

    @staticmethod
    def SetListNext(pos, val):
        return UtmpHead.SetInt(LISTNEXT_POS, pos, val)

    @staticmethod
    def GetListPrev(pos):
        return UtmpHead.GetInt(LISTPREV_POS, pos)

    @staticmethod
    def SetListPrev(pos, val):
        return UtmpHead.SetInt(LISTPREV_POS, pos, val)

    @staticmethod
    def GetNext(pos):
        return UtmpHead.GetInt(NEXT_POS, pos)

    @staticmethod
    def SetNext(pos, val):
        return UtmpHead.SetInt(NEXT_POS, pos, val)

    @staticmethod
    def GetNumber():
        return UtmpHead.GetInt(NUMBER_POS, 0)

    @staticmethod
    def SetNumber(number):
        return UtmpHead.SetInt(NUMBER_POS, 0, number)

    @staticmethod
    def GetUptime():
        return UtmpHead.GetInt(UPTIME_POS, 0)

    @staticmethod
    def SetUptime(uptime):
        return UtmpHead.SetInt(UPTIME_POS, 0, uptime)

    @staticmethod
    def SetReadOnly(readonly):
        UtmpHead.utmphead.detach()
        UtmpHead.utmphead.attach(None, (sysv_ipc.SHM_RDONLY if readonly else 0))

