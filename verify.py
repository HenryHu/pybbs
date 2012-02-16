#!/usr/bin/env python

"""Verify data structures
   by henryhu
   2012.2.4    created.
"""

from Post import Post
from Board import Board
from Session import Session
from BCache import BCache
from Config import Config, UTMP_HASHSIZE, USHM_SIZE
from BoardManager import BoardManager
from User import User
from UCache import UCache
from UserManager import UserManager
from Session import SessionManager
from Auth import Auth
from MsgBox import MsgBox
from FavBoard import FavBoardMgr
from BRead import BReadMgr
import string
from Session import SessionManager                                                                                        
from Util import Util                                                                                                     
from MsgHead import MsgHead                                                                                               
from Utmp import Utmp                                                                                                     
from UtmpHead import UtmpHead                                                                                             
from UserInfo import UserInfo   
from Log import Log
import os

def Init():
    Config.LoadConfig()
    BCache.Init()
    BoardManager.Init()
    UCache.Init()
    Utmp.Init()
    return

def verify():
    verifyUtmpHead();

def dump_userinfo(i):
    userinfo = UserInfo(i)
    print vars(userinfo)

def verifyUtmpHead():
    allset = set()
    for i in range(1, USHM_SIZE):
        allset.add(i)
    ok = True
    i = UtmpHead.GetListHead()
    if (i == 0):
        Log.error("Empty header!")
        return False
    Log.info("head %d" % i)
    listseen = set()
    listseen.add(i)
    i = UtmpHead.GetListNext(i - 1)

    while (i != UtmpHead.GetListHead()):
        Log.info("node %d" % i)
        if (i in listseen):
            Log.error("Repeated! %d" % i)
            ok = False
            break
        if (not Utmp.IsActive(i - 1)):
            Log.error("Inactive item! %d" % i)
            ok = False

        try:
            os.kill(Utmp.GetPid(i-1), 0)
        except:
            Log.error("Process gone! %d" % i)
            ok = False
        listseen.add(i)
        i = UtmpHead.GetListNext(i-1)

    if (ok):
        Log.info("UtmpHead.LIST OK")
    else:
        Log.error("UtmpHead.LIST ERR")

    seen = set()

    for i in range(0, UTMP_HASHSIZE + 1):
        j = UtmpHead.GetHashHead(i)
        if (j == 0):
            continue
        Log.info("hash %d head %d" % (i, j))
        if (i != 0):
            userid = Utmp.GetUserId(j - 1)
            if (userid == ''):
                Log.error("illegal login id! %d" % j)
                ok = False
            else:
                Log.info("userid %s" % userid)
                hash = Utmp.Hash(userid)
                if (hash != i):
                    Log.error("head in wrong list! %d %s %d != %d FIX!" % (j, userid, hash, i))
                    ok = False
                    UtmpHead.SetHashHead(i, 0)
                    continue
        seen.add(j)
        if (i != 0):
            if (not j in listseen):
                Log.error("%d missing in UtmpHead.LIST!" % j)
                ok = False
            else:
                listseen.remove(j)
        cnt = 0

        last = j
        j = UtmpHead.GetNext(j - 1)
        while (j != 0):
            if (i != 0):
                Log.info("hash node %d" % j)
            if (j in seen):
                Log.error("Repeated! %d" % j)
                ok = False
                break
            if (i != 0):
                if (not j in listseen):
                    Log.error("%d missing in UtmpHead.LIST!" % j)
                    ok = False
                else:
                    listseen.remove(j)

            if (i != 0):
                userid = Utmp.GetUserId(j - 1)
                if (userid == ''):
                    Log.error("illegal login id! %d" % j)
                    ok = False
#                    UtmpHead.SetNext(last - 1, 0)
#                    break
                else:
                    Log.info("userid %s" % userid)
                    hash = Utmp.Hash(userid)
                    if (hash != i):
                        Log.error("node in wrong list! %d %s %d != %d" % (j, userid, hash, i))
                        ok = False
                        break
            seen.add(j)
            last = j
            j = UtmpHead.GetNext(j-1)
            cnt += 1
            if (cnt > 20):
                if (i != 0):
                    Log.warn("Hash list too long!")
                    break
        if (i == 0):
            Log.info("freelist len: %d" % cnt)
            if ( cnt < 100):
                Log.error("freelist too short!")
                ok = False
                    

    if (len(listseen) != 0):
        for i in listseen:
            Log.error("%d missing in UtmpHead.HASH!" % i)
            dump_userinfo(i)
            ok = False
    left = allset - seen
    if (len(left) != 0):
        for i in left:
            Log.warn("%d missing in CHAIN!" % i)
    if (ok):
        Log.info("UtmpHead OK")
    else:
        Log.error("UtmpHead ERR")


def main():
    Init()
    verify()
        
if __name__ == '__main__':
    main()   

