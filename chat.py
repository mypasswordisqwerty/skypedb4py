

class Chat:
    def __init__(self,skype,params):
        self.skype=skype
        self.Id=int(params[0])
        self.Name=params[1]
        self.AltName=params[2]
        self.Type=int(params[3])
        self.Topic=params[4]
        self.ActivityTimestamp=params[5] if len(params)>5 and params[5]!=None else 0

    FriendlyName = property(lambda self : self.Topic)
    DialogPartner  = property(lambda self : self.Topic)

    def SendMessage(self,body):
        self.skype.SendMessage(self,body)



class Sender:
    def __init__(self,h,fn):
        self.Handle=h
        self.FullName=fn


class ChatMsg:
    def __init__(self,skype,params):
        self.Id=int(params[0])
        self.FromHandle=params[1]
        self.FromDisplayName=params[2]
        self.Sender=Sender(params[1],params[2])
        self.Body=params[3]
        self.Chat=Chat(skype,params[4:])
        self.ChatName=self.Chat.Name