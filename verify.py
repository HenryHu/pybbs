#!/usr/bin/env python

"""Verify data structures
   by henryhu
   2012.2.4    created.
"""

from Post import Post
from Board import Board
from Session import Session
from BCache import BCache
from Config import Config
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
    return

def verify():
    verifyUtmpHead();

def verifyUtmpHead():
    i = UtmpHead.GetListHead()
    seen = set()

    while (i != UtmpHead.GetListHead()):
        Log.info("%d" % i)
        if (i in seen):
            Log.error("Repeated! %d" % i)
        i = UtmpHead.GetListNext(i)

def main():
    Init()
    verify()
        
if __name__ == '__main__':
    main()   

