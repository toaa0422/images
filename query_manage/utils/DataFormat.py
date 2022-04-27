# 前后端数据格式交互类（为了统一的前后端交互）
import json

class ResDataDict:
    def __init__(self,code=-1,info="",sum=0,data=[]):
        self.code = code      # 数据状态(1:成功，-1:失败)
        self.info = info      # 信息提示
        self.sum = sum        # 返回数据记录大小
        self.data = data      # 返回数据，json数组

    def setCode(self, code):
        self.code = code
    def getCode(self):
        return self.code

    def setInfo(self, info):
        self.info = info
    def getInfo(self):
        return self.info

    def setSum(self, sum):
        self.sum = sum
    def getSum(self):
        return self.sum

    def setData(self, data):
        self.data = data
    def getData(self):
        return self.data

    def addDataItem(self, item):
        self.data.append(item)

    def setStatus(self, code, info):
        self.code = code
        self.info = info

    # 数据类转字符串打印
    def __str__(self):
        ret_dict = {"code":self.code, "info":self.info, "sum":self.sum, "data":self.data}
        return json.dumps(ret_dict)