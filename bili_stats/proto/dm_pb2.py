from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

def _field(message, name, number, field_type, label=1, type_name=None):
    value=message.field.add(); value.name=name; value.number=number; value.label=label; value.type=field_type
    if type_name: value.type_name=type_name

file_proto=descriptor_pb2.FileDescriptorProto(); file_proto.name="bili_stats/proto/dm.proto"; file_proto.package="bilibili.community.service.dm.v1"; file_proto.syntax="proto3"
elem=file_proto.message_type.add(); elem.name="DanmakuElem"
for spec in (("id",1,3),("progress",2,5),("mode",3,5),("fontsize",4,5),("color",5,13),("midHash",6,9),("content",7,9),("ctime",8,3),("weight",9,5),("action",10,9),("pool",11,5),("idStr",12,9),("attr",13,5)): _field(elem,*spec)
segment=file_proto.message_type.add(); segment.name="DmSegMobileReply"; _field(segment,"elems",1,11,3,".bilibili.community.service.dm.v1.DanmakuElem")
config=file_proto.message_type.add(); config.name="DmSegConfig"; _field(config,"pageSize",1,3); _field(config,"total",2,3)
view=file_proto.message_type.add(); view.name="DmWebViewReply"; _field(view,"state",1,5); _field(view,"text",2,9); _field(view,"textSide",3,9); _field(view,"dmSge",4,11,1,".bilibili.community.service.dm.v1.DmSegConfig")
DESCRIPTOR=descriptor_pool.Default().AddSerializedFile(file_proto.SerializeToString())
def _class(name):
    descriptor=DESCRIPTOR.message_types_by_name[name]
    return message_factory.GetMessageClass(descriptor) if hasattr(message_factory,"GetMessageClass") else message_factory.MessageFactory().GetPrototype(descriptor)
DanmakuElem=_class("DanmakuElem"); DmSegMobileReply=_class("DmSegMobileReply"); DmSegConfig=_class("DmSegConfig"); DmWebViewReply=_class("DmWebViewReply")
