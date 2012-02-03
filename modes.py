#/*
    #Pirate Bulletin Board System
    #Copyright (C) 1990, Edward Luke, lush@Athena.EE.MsState.EDU
    #Eagles Bulletin Board System
    #Copyright (C) 1992, Raymond Rocker, rocker@rock.b11.ingr.com
                        #Guy Vega, gtvega@seabass.st.usm.edu
                        #Dominic Tynes, dbtynes@seabass.st.usm.edu
                            # 
    #This program is free software; you can redistribute it and/or modify
    #it under the terms of the GNU General Public License as published by
    #the Free Software Foundation; either version 1, or (at your option)
    #any later version.
#
    #This program is distributed in the hope that it will be useful,
    #but WITHOUT ANY WARRANTY; without even the implied warranty of
    #MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    #GNU General Public License for more details.
#
    #You should have received a copy of the GNU General Public License
    #along with this program; if not, write to the Free Software
    #Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#*/

#/* Lots o' modes! */

IDLE          = 0      # /* Modes a user can be in */
ULDL          = 1      # /* see mode in struct user_info in bbs.h */
TALK          = 2
NEW           = 3
CHAT1         = 4
READNEW       = 5
POSTING       = 6
MAIL          = 7
CHAT2         = 8
CHAT4         = 9
CHAT3         = 10
LAUSERS       = 11
LUSERS        = 12
SMAIL         = 13
RMAIL         = 14
MMENU         = 15
TMENU         = 16
XMENU         = 17
READING       = 18
PAGE          = 19
ADMIN         = 20
READBRD       = 21
SELECT        = 22
LOGIN         = 23
MONITOR       = 24
EDITWELC      = 25
ZAP           = 26
EDITUFILE     = 27
EDITSFILE     = 28
QUERY         = 29
CNTBRDS       = 30
VOTING        = 31
VISIT         = 32
IRCCHAT       = 33
BBSNET        = 34
FOURM         = 35
CSIE_GOPHER   = 36
CSIE_TIN      = 37
CSIE_ANNOUNCE = 38
FRIEND        = 39
YANKING       = 40
EXCE_MJ       = 41
GMENU         = 42
EXCE_BIG2     = 43
EXCE_CHESS    = 44
NOTEPAD       = 45
MSG           = 46
USERDEF       = 47
EDIT          = 48
OFFLINE       = 49
EDITANN       = 50
WWW           = 51
WEBEXPLORE    = WWW
CCUGOPHER     = 52
LOOKMSGS      = 53
WFRIEND       = 54
LOCKSCREEN    = 55
IMAIL	= 56
EDITSIG       = 57
EDITPLAN      = 58
GIVEUPNET= 59
SERVICES= 60
FRIENDTEST= 61
CHICKEN	= 62
QUIZ= 63
KILLER= 64
CALENDAR= 65
CALENEDIT= 66
DICT= 67
CALC= 68
SETACL= 69
EDITOR= 70
HELP= 71
POSTTMPL= 72
