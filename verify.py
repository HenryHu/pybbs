#!/usr/bin/env python

"""Verify data structures
   by henryhu
   2012.2.4    created.
"""

from Post import Post
from Board import Board
from Session import Session
from BCache import BCache
from Config import Config, UTMP_HASHSIZE
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

def Init():
    Config.LoadConfig()
    BCache.Init()
    BoardManager.Init()
    UCache.Init()
    Utmp.Init()
    return

def verify():
    verifyUtmpHead();

def verifyUtmpHead():
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
        listseen.add(i)
        i = UtmpHead.GetListNext(i-1)

    if (ok):
        Log.info("UtmpHead.LIST OK")
    else:
        Log.error("UtmpHead.LIST ERR")

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
                continue
            Log.info("userid %s" % userid)
            hash = Utmp.Hash(userid)
            if (hash != i):
                Log.error("head in wrong list! %d %s %d != %d FIX!" % (j, userid, hash, i))
                ok = False
                UtmpHead.SetHashHead(i, 0)
                continue
        seen = set()
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
                    Log.error("illegal login id! %d FIX" % j)
                    ok = False
                    UtmpHead.SetNext(last - 1, 0)
                    break
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
            if (cnt > 10):
                Log.warn("Hash list too long!")
                break

    if (len(listseen) != 0):
        for i in listseen:
            Log.error("%d missing in UtmpHead.HASH!" % i)
            ok = False
    if (ok):
        Log.info("UtmpHead OK")
    else:
        Log.error("UtmpHead ERR")


def main():
    Init()
    verify()
        
if __name__ == '__main__':
    main()   

