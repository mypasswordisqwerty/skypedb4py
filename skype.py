
import sqlite3
import os,imp,signal
import threading
import time,uuid,binascii
import logging,traceback
from chat import Chat,ChatMsg

log=logging.getLogger("Skype4Py.skype.Skype")


class SkypeThread(threading.Thread):
    INSTANCE=None
    def __init__(self,cmd,dbpath,ids):
        threading.Thread.__init__(self)
        SkypeThread.INSTANCE=self
        self.ids=','.join([str(i) for i in ids])
        self.npid=os.fork()
        self.dbpath=dbpath
        if self.npid==0:
            os.execvp(cmd[0],cmd)
            return
        log.debug("ST pid %d",self.npid)
        self.daemon=True
        self.start()

    def __del__(self):
        SkypeThread.INSTANCE=None

    def run(self):
        db=sqlite3.connect(self.dbpath)
        c=db.cursor()
        i=0
        while i<30:
            c.execute("SELECT count(id) from Messages WHERE type=61 and sending_status=1 and id in ("+self.ids+");")
            num=int(c.fetchone()[0])
            log.debug("ST found %d of %s",num,self.ids)
            if num==0:
                break
            i+=1
            time.sleep(1)
        c.close()
        db.close()
        SkypeThread.kill()
        SkypeThread.INSTANCE=None


    @staticmethod
    def kill():
        if not SkypeThread.INSTANCE:
            return 
        log.debug("ST killing %d",SkypeThread.INSTANCE.npid)
        os.kill(SkypeThread.INSTANCE.npid,signal.SIGTERM)
        del SkypeThread.INSTANCE


class Skype(threading.Thread):
    def __init__(self,Events=None,**Options):
        threading.Thread.__init__(self)
        settings=imp.load_source('settings',"settings.py")
        self.mainpath=os.path.join(os.path.expanduser(settings.RODB),"main.db")
        self.runcmd=settings.SKYPE2_CMD
        self.rwpath=None
        self.events=Events
        self.user=None
        self.userName=None
        self.maxmsg=0
        self.thread=False
        self.stop=True


    def __del__(self):
        self._stop()
        if SkypeThread.INSTANCE:
            SkypeThread.kill()
        if self.db:
            self.db.close()

    def _stop(self):
        if self.thread:
            self.stop=True
            self.join()


    def Attach(self):
        self._stop()
        db=sqlite3.connect(self.mainpath)
        c=db.cursor()
        c.execute("SELECT skypename,fullname FROM Accounts;")
        self.user,self.userName=c.fetchone()
        self.rwpath=os.path.join(os.path.expanduser(self.runcmd[2]),self.user)
        c.execute("SELECT max(id) FROM Messages;")
        self.maxmsg=int(c.fetchone()[0])
        c.close()
        db.close()
        log.debug("loaded %s %s %d",self.user,self.userName,self.maxmsg)
        self.daemon=True
        self.start()
        SkypeThread(self.runcmd,os.path.join(self.rwpath,"main.db"),[299])



    def event(self,name,*args,**kwargs):
        log.debug("event %s %s",name,str(args))
        if self.events and getattr(self.events,name)!=None:
            func=getattr(self.events,name)
            func(*args,**kwargs)


    def run(self):
        self.thread=True
        self.stop=False
        db=sqlite3.connect(self.mainpath)
        c=db.cursor()
        while not self.stop:
            found=False
            mx=self.maxmsg
            c.execute("SELECT t1.id,t1.author,t1.from_dispname,t1.body_xml,t2.id,t2.identity,t2.alt_identity,t2.type,t2.displayname FROM Messages as t1,Conversations as t2 WHERE t2.id=t1.convo_id and t1.body_xml like '!%' and t1.type=61 and t1.id>=?;",(self.maxmsg,))
            for x in c.fetchall():
                mid=int(x[0])
                if mid==self.maxmsg:
                    found=True
                    continue
                log.debug("got message %s",str(x))
                if mid>mx:
                    mx=mid
                msg=ChatMsg(self,x)
                try:
                    self.event("MessageStatus",msg,"SENT")
                except:
                    log.error("Error: %s",traceback.format_exc())
            time.sleep(0.1)
            self.maxmsg=mx
            if found==False:
                c.close()
                db.close()
                db=sqlite3.connect(self.mainpath)
                c=db.cursor()
        c.close()
        db.close()
        self.thread=False

    def SendMessage(self,chat,body):
        while SkypeThread.INSTANCE:
            log.debug("INstance found")
            time.sleep(1)
        db=sqlite3.connect(os.path.join(self.rwpath,"main.db"))
        c=db.cursor()
        tm=int(time.time())
        uid=uuid.uuid4().get_bytes()+uuid.uuid4().get_bytes()
        c.execute("SELECT id,identity,alt_identity FROm Conversations WHERE identity=? or identity=?;",(chat.Name,chat.AltName))
        cht=c.fetchone()
        if cht==None:
            c.close()
            db.close()
            raise Exception("Chat not found "+str(chat.Id)+":"+chat.Topic)
        crc=binascii.crc32(body.encode("utf-8"))
        if crc<0:
            crc=-crc-1
        c.execute("INSERT INTO Messages(is_permanent,convo_id,chatname,author,from_dispname,guid,timestamp,type,sending_status,body_xml,chatmsg_type,chatmsg_status,body_is_rawxml,crc) "+
            "VALUES(1,?,?,?,?,?,?,61,1,?,3,2,1,?);",(int(cht[0]),cht[1],self.user,self.userName,sqlite3.Binary(uid),tm,body,crc))
        rid=c.lastrowid
        c.execute("UPDATE Messages set dialog_partner=?,remote_id=? WHERE id=?;",(cht[2] if cht[2] else cht[1],rid,rid))
        log.debug("sending msg %d:%s",rid,body)
        c.close()
        db.commit()
        db.close()
        db=sqlite3.connect(os.path.join(self.rwpath,"msn.db"))
        c=db.cursor()
        c.execute("INSERT INTO queue(type,status,message_oid,legacy_str,timestamp,recipient,threadactiondata,sendalways,flags) "+
            "VALUES(0,0,?,'',?,?,'',1,0);",((rid<<5)+9,tm,cht[2] if cht[2] else cht[1]))
        c.close()
        db.commit()
        db.close()
        SkypeThread(self.runcmd,os.path.join(self.rwpath,"main.db"),[rid])



    def _GetChats(self):
        db=sqlite3.connect(self.mainpath)
        c=db.cursor()
        c.execute("SELECT id,identity,alt_identity,type,displayname,last_activity_timestamp FROM Conversations;")
        res=[]
        for x in c.fetchall():
            #log.debug("found chat %s",str(x))
            res+=[Chat(self,x)]
        c.close()
        db.close()
        log.debug("found %d chats",len(res))
        return res

    Chats = property(_GetChats)
