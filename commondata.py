import struct
from sysv_ipc import SharedMemory, ExistentialError, SHM_RDONLY

from Util import Util
import UtmpHead
from Log import Log
import Config
from cstruct import *

'''
struct public_data {
    time_t nowtime;
    int sysconfimg_version;
    int www_guest_count;
    unsigned int max_user;
    unsigned int max_wwwguest;
#ifdef FLOWBANNER
        int bannercount;
        char banners[MAXBANNER][BANNERSIZE];
#else
    char unused[1004];
#endif
};
'''

NOWTIME_POS = 0
SYSCONFIMG_VERSION_POS = NOWTIME_POS + 4
WWW_GUEST_COUNT_POS = SYSCONFIMG_VERSION_POS + 4
MAX_USER_POS = WWW_GUEST_COUNT_POS + 4
MAX_WWWGUEST_POS = MAX_USER_POS + 4
UNUSED_POS = MAX_WWWGUEST_POS + 4

PUBLICSHM_SIZE = UNUSED_POS + 1004

@init_fields
class CommonData:
    _fields = [
        ['nowtime', I32()],
        ['sysconfimg_version', I32()],
        ['www_guest_count', I32()],
        ['max_user', U32()],
        ['max_wwwguest', U32()],
        ['unused', FixStr(1004)],
    ]
    publicshm = None

    def read(self, pos, len):
        return CommonData.publicshm.read(len, pos)

    def write(self, pos, data):
        CommonData.publicshm.write(data, pos)

    @staticmethod
    def SaveMaxUser():
        CommonData().max_user = UtmpHead.UtmpHead.GetNumber() + CommonData().www_guest_count
        CommonData().max_wwwguest = CommonData().www_guest_count
        with open(Config.BBS_ROOT + "etc/maxuser", "w") as fmaxuser:
            fmaxuser.write("%d %d" % (CommonData().max_user, CommonData().max_wwwguest))

    @staticmethod
    def UpdateMaxUser():
        if (UtmpHead.UtmpHead.GetNumber() + CommonData().www_guest_count > CommonData().max_user):
            CommonData.SetReadonly(0)
            CommonData.SaveMaxUser()
            CommonData.SetReadonly(1)

    @staticmethod
    def Init():
        if (CommonData.publicshm == None):
            try:
                CommonData.publicshm = SharedMemory(Config.PUBLIC_SHMKEY, size = PUBLICSHM_SIZE)
            except ExistentialError:
                Log.Error("time daemon not started")
                raise Exception("Initialization failed: publicshm not created")

    @staticmethod
    def SetReadonly(readonly):
        CommonData.publicshm.detach()
        CommonData.publicshm.attach(None, (SHM_RDONLY if readonly else 0))

