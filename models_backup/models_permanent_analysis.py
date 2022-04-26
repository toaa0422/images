from django.db import models
import pymysql
import logging
import time
from prober_manage.settings import MYSQL_CONNECTION_CONF, logger
from query_manage.utils.DataFormat import ResDataDict


# 数据库操作模块
class AccessControl(models.Model):
    """
    自定义权限控制
    """

    class Meta:
        permissions = (
            ('access_analytic_statistic', u'分析统计'),
        )


# 数据库执行
# 参数：
#       sqlcmd:数据库语句
#       reltype:返回数据库类型
# 返回：数据库执行的结果
def sqlcmd_excute(sqlcmd, reltype=list):
    try:
        # 链接数据库
        conn = pymysql.connect(**MYSQL_CONNECTION_CONF)
        # 游标设置为列表类型
        if reltype == 'dict':
            cur = conn.cursor(cursor=pymysql.cursors.DictCursor)
        else:
            cur = conn.cursor()

        # 执行搜索
        cur.execute(sqlcmd)
        # 获取搜索结果
        result_list = cur.fetchall()
        # 关闭资源
        conn.close()
        cur.close()
        # 返回搜索结果
        return result_list

    except pymysql.Error:
        # 异常记录
        logger.error(sqlcmd + "\n")
        return None


####################################### 辅助功能 ################################################################

# 判断MAC表是否存在
def table_isexist(table):
    sqlcmd = "show tables like 'imsi_%s';" % (table)
    status = sqlcmd_excute(sqlcmd)
    if status:
        return True
    return False


# 返回所有存在的站点名称列表
def station_list_get():
    sqlcmd = "select site_name from devices where site_name is not null;"
    stat_list = sqlcmd_excute(sqlcmd)
    return stat_list

# 返回所有存在的站点名称列表+新设备 new
def station_list_get_new():
    sqlcmd = "select site_name from bcell_devices where site_name is not null;"
    stat_list = sqlcmd_excute(sqlcmd)
    return stat_list


# 返回所有存在的站点名称和MAC地址字典的列表
def station_mac_dict_list_get():
    sqlcmd = "select site_name as station,mac from devices where site_name is not null;"
    stat_list = sqlcmd_excute(sqlcmd, "dict")
    return stat_list


# 根据地址和站点信息返回MAC地址列表
# 参数：site_name:站点名称, address:站点地址
# 返回：返回所有站点的MAC地址列表
def search_mac_list_by_station(site_name=None, address=None):
    # 构建数据库语句
    if site_name:
        if address:
            sqlcmd = "select mac from devices where site_name='%s' and site_address_area='%s';" \
                     % (site_name, address)
        else:
            sqlcmd = "select mac from devices where site_name='%s';" % (site_name)
    else:
        sqlcmd = "select mac from devices where site_name is not null;"

    # 执行数据库命令
    data_list = sqlcmd_excute(sqlcmd)

    # 如果搜索数据为空，直接返回空列表
    mac_list = []
    if data_list:
        for data in data_list:  # 构建MAC地址列表
            mac_list.append(data[0])
    return mac_list

#同上 +新设备
def search_mac_list_by_station_new(site_name=None, address=None):
    # 构建数据库语句
    if site_name:
        if address:
            sqlcmd = "select mac,sn from bcell_devices where site_name='%s' and site_address_area='%s';" \
                     % (site_name, address)
        else:
            sqlcmd = "select mac,sn from bcell_devices where site_name='%s';" % (site_name)
    else:
        sqlcmd = "select mac,sn from bcell_devices where site_name is not null;"

    # 执行数据库命令
    data_list = sqlcmd_excute(sqlcmd)

    # 如果搜索数据为空，直接返回空列表
    mac_list = []
    sn_list=[]
    if data_list:
        for data in data_list:  # 构建MAC地址列表
            mac_list.append(data[0])
            sn_list.append(data[1])
    return mac_list[0],sn_list[0]


# 根据MAC地址返回站点名称
def search_station_by_mac(mac):
    if mac:
        # 从devices表中取，devices表中包括所有注册或未注册的设备，而site_info表中存的都是已注册的设备
        sqlcmd = "select site_name from devices where mac='%s';" % (mac)
        site_list = sqlcmd_excute(sqlcmd, "dict")
        if site_list:
            return site_list[0]

    return {'site_name': ""}


# 根据站点名称返回MAC地址
def search_mac_by_station(site_name):
    if site_name:
        # 从devices表中取，devices表中包括所有注册或未注册的设备，而site_info表中存的都是已注册的设备
        sqlcmd = "select mac from devices where site_name='%s';" % (site_name)
        tmp_list = sqlcmd_excute(sqlcmd, "dict")
        if tmp_list:
            return tmp_list[0]["mac"]
    return None


########################################## 详细搜索 ##################################################################
# 通过搜索获取信息
# 参数：
#     time_from:起始时间
#     time_end:终止时间
#     mac_list:需要搜索的MAC地址列表
#     imsi_list:需要组合查询的IMSI列表
#     pagefrom:分页的起始页
#     recordsLimt:每页的记录数量(默认每页30)
#     orderby:根据指定选项排序
#     orderdir:排序方向(递增:"asc",默认)(递减:"desc")
# 返回：一个包含每条记录字典组成的列表
def get_data_by_search(time_from, time_end, mac_list, imsi_list, pagefrom, recordsLimt=30, orderby=None,
                       orderdir="asc"):
    # 计算实际的记录起始位置
    if pagefrom < 1:
        pagefrom = 1
    pagefrom = (pagefrom - 1) * recordsLimt

    # 判断输入的关键参数存不存在，若不存在则无法搜索，直接返回空
    if (mac_list == []) or (not time_from) or (not time_end):
        return None

    # 申请数据库执行语句
    sqlcmds = ""
    info_list = []

    # 构建搜索语句
    for mac in mac_list:
        # 总体语句构建
        sqlcmds = ''.join((sqlcmds,
                           "(select imsi_%s.*,devices.site_name,imsiaddr.address,imsiaddr.type as operator from imsi_%s " \
                           "left join devices on devices.mac='%s' " \
                           "left join imsiaddr on imsi_%s.phone_num=imsiaddr.phone_num " \
                           "where imsi_%s.capture_time>='%s' and imsi_%s.capture_time<'%s' " \
                           % (mac, mac, mac, mac, mac, time_from, mac, time_end)
                           ))
        # 如果IMSI列表不为空，添加and并列
        if imsi_list != []:
            sqlcmds = ''.join((sqlcmds, ' and ('))
            for imsi in imsi_list:  # 循环添加到每一条语句中去
                sqlcmds = ''.join((sqlcmds, "imsi_%s.imsi like '%%%s%%'" % (mac, imsi)))
                if imsi != imsi_list[-1]:  # 判断是否为最后一个元素
                    sqlcmds = ''.join((sqlcmds, " or "))
                else:
                    sqlcmds = ''.join((sqlcmds, ")"))

        # 若MAC列表中有多个元素则循环构建
        if mac != mac_list[-1]:
            sqlcmds = ''.join((sqlcmds, " ) union all "))
        else:
            sqlcmds = ''.join((sqlcmds, " ) "))

    # 若有排序选项则添加排序
    if orderby:
        sqlcmds = ''.join((sqlcmds, 'order by %s' % (orderby)))
    # 若有正反序则添加方向
    if orderdir.lower() == 'desc':
        sqlcmds = ''.join((sqlcmds, " %s " % (orderdir.lower())))
    # 添加分页选项和分号结尾
    sqlcmds = ''.join((sqlcmds, ' limit %s,%s;' % (pagefrom, recordsLimt)))

    # print(sqlcmds)
    # 执行语句
    try:
        # 链接数据库
        conn = pymysql.connect(**MYSQL_CONNECTION_CONF)
        # 游标设置为列表类型
        cur = conn.cursor(cursor=pymysql.cursors.DictCursor)
        # 执行搜索
        cur.execute(sqlcmds)
        # 获取搜索结果
        info_list = cur.fetchall()
        # 关闭资源
        conn.close()
        cur.close()
    except pymysql.Error as e:
        # 异常记录
        logger.error(sqlcmds + str(e))

    # 返回搜索结果
    return info_list


# 获取详细搜索数据的总数目（用于分页）
# 参数：
#     time_from:起始时间
#     time_end:终止时间
#     mac_list:需要搜索的MAC地址列表
#     imsi_list:需要组合查询的IMSI列表
# 返回：符合条件的记录的总数
def get_count_by_search(time_from, time_end, mac_list, imsi_list):
    # 判断输入的关键参数存不存在，若不存在则无法搜索，直接返回空
    if (mac_list == []) or (not time_from) or (not time_end):
        return 0

    # 申请数据库执行语句
    sqlcmds = ""
    total_counts = 0

    # 构建搜索语句
    for mac in mac_list:
        # 总体语句构建
        sqlcmds = ''.join((sqlcmds,
                           "(select count(1) from imsi_%s where capture_time>='%s' and capture_time<'%s' " \
                           % (mac, time_from, time_end)
                           ))
        # 如果IMSI列表不为空，添加and并列
        if imsi_list != []:
            sqlcmds = ''.join((sqlcmds, ' and ('))
            for imsi in imsi_list:  # 循环添加到每一条语句中去
                sqlcmds = ''.join((sqlcmds, "imsi_%s.imsi like '%%%s%%'" % (mac, imsi)))
                if imsi != imsi_list[-1]:  # 判断是否为最后一个元素
                    sqlcmds = ''.join((sqlcmds, " or "))
                else:
                    sqlcmds = ''.join((sqlcmds, ")"))

        # 若MAC列表中有多个元素则循环构建
        if mac != mac_list[-1]:
            sqlcmds = ''.join((sqlcmds, " ) union all "))
        else:
            sqlcmds = ''.join((sqlcmds, " ); "))

    # print(sqlcmds)
    # 执行语句
    try:
        # 链接数据库
        conn = pymysql.connect(**MYSQL_CONNECTION_CONF)
        # 游标设置为列表类型
        cur = conn.cursor()
        # 执行搜索
        cur.execute(sqlcmds)
        # 获取搜索结果
        count_list = cur.fetchall()
        # 如果出错直接返回0
        if not count_list:
            return 0
        # 遍历整个列表，计算总和
        for count in count_list:
            total_counts += count[0]

        # 关闭资源
        conn.close()
        cur.close()
    except pymysql.Error:
        # 异常记录
        logger.error(sqlcmds + "\n")

    # 返回搜索结果
    return total_counts


# 获取导出信息列表
# 参数：
#     mac:需要搜索的MAC表
#     station:需要搜索的站点名
#     time_from:起始时间
#     time_end:终止时间
#     imsi_list:需要组合查询的IMSI列表
#     addr:地址信息
# 返回：以IMSI为行进行统计各个模块数量的列表，用于导出EXCEL文件
def get_test_export_data(mac, station, time_from, time_end, imsi_list, addr):
    # 如果MAC和站点都为空的话直接返回
    if not mac and not station:
        return []

    # 如果imsi_list为空直接返回
    if not imsi_list:
        return []

    # 定义返回数据数组
    info_list = []
    sqlcmd = ""

    try:
        # 链接数据库
        conn = pymysql.connect(**MYSQL_CONNECTION_CONF)
        # 游标设置为列表类型
        cur = conn.cursor(cursor=pymysql.cursors.DictCursor)
        # 如果站点存在则先将站点名称转化为MAC地址
        # 如果站点和MAC同时存在则以MAC地址为准
        if not mac and station:
            if addr:
                sqlcmd = "select device_mac from site_info where site_name='%s' and site_address_area='%s';" % (
                station, addr)
            else:
                sqlcmd = "select device_mac from site_info where site_name='%s';" % (station)
            cur.execute(sqlcmd)
            tmp_list = cur.fetchall()
            if tmp_list:
                mac = tmp_list[0]['device_mac']
                mac = str(mac)
                mac = mac[0:12]  # 兼容wifi+4G双设备同一站点名的情况
            else:  # 既没有mac,站点也找不到,就直接退出,这边需要关闭资源才能退出
                # 关闭资源
                logger.error(sqlcmd)
                conn.close()
                cur.close()
                return []

        # 根据实际数据进行统计
        for i in imsi_list:
            sqlcmd = "select modelCode,count(modelCode) as count from imsi_%s where capture_time>='%s' and capture_time<='%s' and imsi='%s' group by modelCode;" \
                     % (mac, time_from, time_end, i)
            cur.execute(sqlcmd)
            tmp_list = cur.fetchall()
            # 初始化临时字典中数据
            tmp_dict = {}  # 用于存储每个IMSI统计信息的空字典
            tmp_dict['imsi'] = i
            tmp_dict['total_count'] = 0  # 所有数据总和
            tmp_dict['mobile_count'] = 0  # 移动数据总和
            tmp_dict['telecom_count'] = 0  # 电信数据总和
            tmp_dict['unicom_count'] = 0  # 联通数据总和
            tmp_dict['mobileD'] = 0  # 移动D频, 7
            tmp_dict['mobileE'] = 0  # 移动E频, 8
            tmp_dict['mobileF'] = 0  # 移动F频, 9
            tmp_dict['telecomB1'] = 0  # 电信Band1, 10
            tmp_dict['unicomB1'] = 0  # 联通Band1, 11
            tmp_dict['telecomB3'] = 0  # 电信Band3, 12
            tmp_dict['unicomB3'] = 0  # 联通Band3, 13
            tmp_dict['mobileE_indoor'] = 0  # 移动E频(室内), 16
            # 如果搜索结果有数据则添加
            if tmp_list:
                for t in tmp_list:
                    if t['modelCode'] == 7:
                        tmp_dict['mobileD'] = t['count']
                        tmp_dict['mobile_count'] += t['count']
                    if t['modelCode'] == 8:
                        tmp_dict['mobileE'] = t['count']
                        tmp_dict['mobile_count'] += t['count']
                    if t['modelCode'] == 9:
                        tmp_dict['mobileF'] = t['count']
                        tmp_dict['mobile_count'] += t['count']
                    if t['modelCode'] == 16:
                        tmp_dict['mobileE_indoor'] = t['count']
                        tmp_dict['mobile_count'] += t['count']
                    if t['modelCode'] == 10:
                        tmp_dict['telecomB1'] = t['count']
                        tmp_dict['telecom_count'] += t['count']
                    if t['modelCode'] == 12:
                        tmp_dict['telecomB3'] = t['count']
                        tmp_dict['telecom_count'] += t['count']
                    if t['modelCode'] == 11:
                        tmp_dict['unicomB1'] = t['count']
                        tmp_dict['unicom_count'] += t['count']
                    if t['modelCode'] == 13:
                        tmp_dict['unicomB3'] = t['count']
                        tmp_dict['unicom_count'] += t['count']

                    if t['modelCode'] == 17:  # 0x11
                        tmp_dict['mobileD'] = t['count']
                        tmp_dict['mobile_count'] += t['count']
                    if t['modelCode'] == 18:  # 0x12
                        tmp_dict['mobileE'] = t['count']
                        tmp_dict['mobile_count'] += t['count']
                    if t['modelCode'] == 19:  # 0x13
                        tmp_dict['mobileF'] = t['count']
                        tmp_dict['mobile_count'] += t['count']
                    if t['modelCode'] == 20:  # 0x14
                        tmp_dict['telecomB1'] = t['count']
                        tmp_dict['telecom_count'] += t['count']
                    if t['modelCode'] == 21:  # 0x15
                        tmp_dict['unicomB1'] = t['count']
                        tmp_dict['unicom_count'] += t['count']
                    if t['modelCode'] == 22:  # 0x16
                        tmp_dict['telecomB3'] = t['count']
                        tmp_dict['telecom_count'] += t['count']
                    if t['modelCode'] == 23:  # 0x17
                        tmp_dict['unicomB3'] = t['count']
                        tmp_dict['unicom_count'] += t['count']

                    tmp_dict['total_count'] += t['count']
            # 将字典中数据写入返回列表中
            info_list.append(tmp_dict)

        # 关闭资源
        conn.close()
        cur.close()
    except pymysql.Error:
        # 异常记录
        logger.error(sqlcmd + "\n")

    # 返回搜索结果
    return info_list


def get_search_export_sqlcmd(mac_list, imsi_list, time_from, time_end):
    sqlcmd = ""
    for mac in mac_list:
        if imsi_list:
            imsi_str = "and ( "
            for imsi in imsi_list:
                if imsi != imsi_list[-1]:
                    imsi_str = ''.join((imsi_str, "imsi='%s' or " % (imsi)))
                else:
                    imsi_str = ''.join((imsi_str, "imsi='%s' " % (imsi)))
            sqlcmd = "select capture_time,imsi,imei,rssi from imsi_%s " \
                     "where capture_time>='%s' and capture_time<'%s' %s ) order by capture_time asc;" \
                     % (mac, time_from, time_end, imsi_str)
        else:
            sqlcmd = "select capture_time,imsi,imei,rssi from imsi_%s " \
                     "where capture_time>='%s' and capture_time<'%s' order by capture_time asc;" \
                     % (mac, time_from, time_end)
    return sqlcmd


# 获取导出信息列表
# 参数：
#     mac_list:需要搜索的MAC列表
#     imsi_list:需要组合查询的IMSI列表
#     time_from:起始时间
#     time_end:终止时间
# 返回：以IMSI为行进行统计各个模块数量的列表，用于导出EXCEL文件
def get_search_export_data(mac_list, imsi_list, time_from, time_end):
    # 如果MAC和站点都为空的话直接返回
    if not mac_list:
        return []

    # 定义返回数据数组
    info_list = []
    sqlcmd = ""

    try:
        # 链接数据库
        conn = pymysql.connect(**MYSQL_CONNECTION_CONF)
        # 游标设置为列表类型
        cur = conn.cursor(cursor=pymysql.cursors.DictCursor)

        # 如果站点存在则先将站点名称转化为MAC地址
        for mac in mac_list:
            if imsi_list:
                imsi_str = "and ( "
                for imsi in imsi_list:
                    if imsi != imsi_list[-1]:
                        imsi_str = ''.join((imsi_str, "imsi='%s' or " % (imsi)))
                    else:
                        imsi_str = ''.join((imsi_str, "imsi='%s' " % (imsi)))
                sqlcmd = "select capture_time,imsi,imei,rssi from imsi_%s where capture_time>='%s' and capture_time<'%s' %s ) order by capture_time asc;" % (
                mac, time_from, time_end, imsi_str)
            else:
                sqlcmd = "select capture_time,imsi,imei,rssi from imsi_%s where capture_time>='%s' and capture_time<'%s' order by capture_time asc;" % (
                mac, time_from, time_end)

            cur.execute(sqlcmd)
            tmp_list = cur.fetchall()
            if tmp_list:
                info_list.extend(tmp_list)

        # 关闭资源
        conn.close()
        cur.close()
    except pymysql.Error:
        # 异常记录
        logger.error(sqlcmd + "\n")

    # 返回搜索结果
    return info_list


###################################### 地图搜索功能 #####################################################################
# 获取地图IMSI搜索数据数组
# 参数：
#       imsi:需要查询的IMSI号
#       time_from:起始时间
#       time_end:终止时间
#       pagefrom:分页的起始页
#       recordsLimt:每页的记录数量(默认每页30)
#       orderby:根据指定选项排序
#       orderdir:排序方向(递增:"asc",默认)(递减:"desc")
# 返回：
#       station_list: 站点信息列表
#       info_list:当前显示的查询信息列表
#       total_records:符合条件的记录总数
def get_datas_by_map_search(imsi, time_from, time_end, pagefrom, recordsLimt=30, orderby=None, orderdir="asc"):
    # 计算实际的记录起始位置
    if pagefrom < 1:
        pagefrom = 1
    pagefrom = (pagefrom - 1) * recordsLimt

    # 判断输入的关键参数存不存在，若不存在则无法搜索，直接返回空
    if (not imsi) or (not time_from) or (not time_end):
        return [], [], 0

    # 获取所有站点的名称,MAC,经度纬度(经纬度只有在site_info 表中有准确数据，而site_info表中不能代表所有的devices,有可能有的站点只有名字但没绑定设备,这样的设置我们不能用)
    sqlcmd = "select devices.site_name,site_info.device_mac,site_info.latitude,site_info.longitude from devices left join site_info on devices.mac=site_info.device_mac where devices.site_name is not null ;"
    device_list = sqlcmd_excute(sqlcmd, "dict")
    if not device_list:
        return [], [], 0

    # 定义返回数据数组
    station_list = []
    info_list = []
    total_count = 0
    sqlcmd = ""

    try:
        # 链接数据库
        conn = pymysql.connect(**MYSQL_CONNECTION_CONF)
        # 游标设置为列表类型
        cur = conn.cursor(cursor=pymysql.cursors.DictCursor)

        # 先算数量，找到有信息的站点
        for d in device_list:
            # 计算站点中IMSI好数据总数
            sqlcmd = "select count(1) from imsi_%s where capture_time>='%s' and capture_time<'%s' and imsi='%s';" % (
            d['device_mac'], time_from, time_end, imsi)
            cur.execute(sqlcmd)
            tmp_list = cur.fetchall()
            if tmp_list:
                count = tmp_list[0]["count(1)"]
                total_count += count
                if count > 0:  # 如果有数据则将该站点信息存储到 station_list 中
                    # 找出该IMSI号在站点的第一次出现的捕获时间(用于地图轨迹)
                    sqlcmd = "select capture_time as first_capture_time from imsi_%s where capture_time>='%s' and capture_time<'%s' and imsi='%s' limit 1;" % (
                    d['device_mac'], time_from, time_end, imsi)
                    cur.execute(sqlcmd)
                    tmp_capture_time_list = cur.fetchall()
                    d.update(tmp_capture_time_list[0])
                    station_list.append(d)

        # 如果所有站点中记录都为0，就直接返回
        if total_count == 0:
            conn.close()  # 关闭资源,!!
            cur.close()
            return station_list, info_list, total_count

        # 最后再去查询显示信息
        sqlcmd = ""  # 清空
        for d in station_list:
            # 总体语句构建
            sqlcmd = ''.join((sqlcmd,
                              "(select imsi_%s.*, '%s' as site_name, imsiaddr.address, imsiaddr.type as operator from imsi_%s " \
                              "left join imsiaddr on imsi_%s.phone_num=imsiaddr.phone_num " \
                              "where imsi_%s.capture_time>='%s' and imsi_%s.capture_time<'%s' and imsi_%s.imsi='%s' " \
                              % (d['device_mac'], d['site_name'], d['device_mac'], d['device_mac'], d['device_mac'],
                                 time_from, d['device_mac'], time_end, d['device_mac'], imsi)
                              ))

            # 若MAC列表中有多个元素则循环构建
            if d != station_list[-1]:
                sqlcmd = ''.join((sqlcmd, ") union all "))
            else:
                sqlcmd = ''.join((sqlcmd, ")"))

        # 若有排序选项则添加排序
        if orderby:
            sqlcmd = ''.join((sqlcmd, 'order by %s' % (orderby)))
        # 若有正反序则添加方向
        if orderdir.lower() == 'desc':
            sqlcmd = ''.join((sqlcmd, " %s " % (orderdir.lower())))
        # 添加分页选项和分号结尾
        sqlcmd = ''.join((sqlcmd, ' limit %s,%s;' % (pagefrom, recordsLimt)))
        cur.execute(sqlcmd)
        info_list = cur.fetchall()
        info_list = list(info_list)

        # 关闭资源
        conn.close()
        cur.close()
    except pymysql.Error:
        # 异常记录
        logger.error(sqlcmd + "\n")

    return station_list, info_list, total_count


# 新设备 查找功能
def get_datas_by_map_search_new(imsi, time_from, time_end, pagefrom, recordsLimt=30, orderby=None, orderdir="asc"):
    # 计算实际的记录起始位置
    if pagefrom < 1:
        pagefrom = 1
    pagefrom = (pagefrom - 1) * recordsLimt

    # 定义返回数据数组
    station_list = []
    info_list = []
    total_count = 0
    sqlcmd = ""
    sql_check_list = []
    try:
        # 链接数据库
        conn = pymysql.connect(**MYSQL_CONNECTION_CONF)
        # 游标设置为列表类型
        cur = conn.cursor(cursor=pymysql.cursors.DictCursor)

        # 先算数量，找到有信息的站点
        sqlcmd = "select sn,site_name,mac as device_mac,longitude,latitude from bcell_devices;"
        device_list = sqlcmd_excute(sqlcmd, "dict")
        for each_device in device_list:
            sqlcmd = "select count(1) from bcell_imsi where sn='%s' and capture_time>='%s' and capture_time<'%s' and imsi='%s';" % (
            each_device['sn'], time_from, time_end, imsi)
            cur.execute(sqlcmd)
            tmp_list = cur.fetchall()

            if tmp_list:
                count = tmp_list[0]['count(1)']
                total_count += count
                if count > 0:
                    sqlcmd = "select capture_time as first_capture_time from bcell_imsi where imsi='%s' and sn='%s' and capture_time>='%s' and capture_time<'%s' limit 1;" % (
                        imsi, each_device['sn'], time_from, time_end)
                    sql_check_list.append(sqlcmd)
                    cur.execute(sqlcmd)
                    tmp_capture_time_list = cur.fetchall()
                    sql_check_list.append(tmp_capture_time_list)
                    each_device.update(tmp_capture_time_list[0])
                    sql_check_list.append(each_device)
                    station_list.append(each_device)
        # 如果所有站点中记录都为0，就直接返回
        if total_count == 0:
            conn.close()  # 关闭资源,!!
            cur.close()
            return [], info_list, total_count

        sqlcmd = "select capture_time,site_name,rpt_time,rssi,bcell_imsi.sn from bcell_imsi LEFT join bcell_devices on bcell_imsi.sn=bcell_devices.sn where capture_time>='%s' and capture_time<'%s' and imsi='%s' " % (
        time_from, time_end, imsi)

        # 若有排序选项则添加排序
        if orderby:
            sqlcmd = ''.join((sqlcmd, 'order by %s' % (orderby)))
        # 若有正反序则添加方向
        if orderdir.lower() == 'desc':
            sqlcmd = ''.join((sqlcmd, " %s " % (orderdir.lower())))
        # 添加分页选项和分号结尾
        sqlcmd = ''.join((sqlcmd, ' limit %s,%s;' % (pagefrom, recordsLimt)))
        sql_check_list.append(sqlcmd)
        cur.execute(sqlcmd)
        info_list = cur.fetchall()

        # 关闭资源
        conn.close()
        cur.close()
    except pymysql.Error:
        # 异常记录
        logger.error(sqlcmd + "\n")
    return station_list, info_list, total_count


###################################### 统计查询 ############################################################

# 统计数据函数(不分页)
# 参数：
#       gran_cycle:统计力度(by_day,by_hour,by_min)
#       mac:mac地址,
#       time_from:统计起始时间,
#       time_end:统计终止时间
# 返回：
#       统计选项的列表,
# 统计选项：IMSI总数量,移动D频,移动E频,移动F频,电信Band1,联通Band1,电信Band1,联通Band1,
#                      移动总和,联通总和,电信总和,其他运营商总和
# 键名：   total_count,mobileD,mobileE,mobileF,telecomB1,unicomB1,telecomB3,unicomB3,
#                      china_mobile,china_unicom,china_telecom,other_operators
def statistics_by_search(gran_cycle, mac, time_from, time_end):
    # 根据统计力度，修改下统计时间字符串（即去掉部分数据）
    if gran_cycle == 'by_day':
        recordsLimt = 30
        interval = 24 * 3600
        time_from = time.strftime("%Y-%m-%d 00:00:00", time.strptime(time_from, "%Y-%m-%d %H:%M:%S"))
        # time_end = time.strftime("%Y-%m-%d 00:00:00", time.strptime(time_end, "%Y-%m-%d %H:%M:%S"))
    # 以小时为单位统计
    elif gran_cycle == 'by_hour':
        recordsLimt = 24
        interval = 3600
        time_from = time.strftime("%Y-%m-%d %H:00:00", time.strptime(time_from, "%Y-%m-%d %H:%M:%S"))
        time_end = time.strftime("%Y-%m-%d %H:00:00", time.strptime(time_end, "%Y-%m-%d %H:%M:%S"))
    # 以分钟为单位统计
    elif gran_cycle == 'by_min':
        recordsLimt = 60
        interval = 60
        time_from = time.strftime("%Y-%m-%d %H:%M:00", time.strptime(time_from, "%Y-%m-%d %H:%M:%S"))
        time_end = time.strftime("%Y-%m-%d %H:%M:00", time.strptime(time_end, "%Y-%m-%d %H:%M:%S"))
    else:
        return []

    # 定义一个返回数据空列表（里面为字典结构）
    statistic_list = []

    # 先判断该mac是否存在
    if not table_isexist(mac):
        return statistic_list

    # 计算开始、结束时间转出的时间戳
    from_second = time.mktime(time.strptime(time_from, "%Y-%m-%d %H:%M:%S"))
    end_second = time.mktime(time.strptime(time_end, "%Y-%m-%d %H:%M:%S"))
    # 计算时间起始终止时间是否小于时间间隔
    if end_second - from_second < interval:
        print("interval too short!")
        return statistic_list

    # 遍历计算
    for i in range(recordsLimt):
        tmp_second = time.mktime(time.strptime(time_from, "%Y-%m-%d %H:%M:%S"))
        tmp_from_second = tmp_second + interval * i
        if tmp_from_second > end_second:  # 角标时间大于终止时间表示结束，退出循环
            break
        elif tmp_from_second < end_second - interval:  # 如果角标时间大于终止时间的一个间隔
            tmp_end_second = tmp_from_second + interval
        else:  # 这是最后一个统计记录
            tmp_end_second = end_second
        tmp_from_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tmp_from_second))
        tmp_end_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tmp_end_second))

        # 定义字典变量
        tmp_dict = {}

        # 增加表项数据，即统计时间
        tmp_dict['entry'] = tmp_from_str

        # 分组统计
        sqlcmd = "select modelCode,count(1) as count from imsi_%s where capture_time>='%s' and capture_time<='%s' group by modelCode;" \
                 % (mac, tmp_from_str, tmp_end_str)
        counts_list = sqlcmd_excute(sqlcmd, "dict")

        # 初始化数据，(一定要做，因为数据不存在时，counts_list中啥都没有)
        tmp_dict['total_count'] = 0
        tmp_dict['mobileD'] = 0  # 移动D频
        tmp_dict['mobileE'] = 0  # 移动E频
        tmp_dict['mobileF'] = 0  # 移动F频
        tmp_dict['telecomB1'] = 0  # 电信Band1
        tmp_dict['unicomB1'] = 0  # 联通Band1
        tmp_dict['telecomB3'] = 0  # 电信Band3
        tmp_dict['unicomB3'] = 0  # 联通Band3
        tmp_dict['gsm'] = 0  # 联通Band3
        tmp_dict['mobileE_indoor'] = 0  # 移动E频(室内)

        # 分组统计
        for i in counts_list:
            # 统计总数
            tmp_dict['total_count'] += i['count']
            # 统计 mobileD
            if i['modelCode'] == 7:
                tmp_dict['mobileD'] = i['count']
            # 统计 mobileE
            elif i['modelCode'] == 8:
                tmp_dict['mobileE'] = i['count']
            # 统计 mobileF
            elif i['modelCode'] == 9:
                tmp_dict['mobileF'] = i['count']
            # 统计 telecomB1
            elif i['modelCode'] == 10:
                tmp_dict['telecomB1'] = i['count']
            # 统计 unicomB1
            elif i['modelCode'] == 11:
                tmp_dict['unicomB1'] = i['count']
            # 统计 telecomB3
            elif i['modelCode'] == 12:
                tmp_dict['telecomB3'] = i['count']
            # 统计 unicomB3
            elif i['modelCode'] == 13:
                tmp_dict['unicomB3'] = i['count']
            elif i['modelCode'] == 24:
                tmp_dict['gsm'] = i['count']
            # 统计 mobileE(indoor)
            elif i['modelCode'] == 16:
                tmp_dict['mobileE_indoor'] = i['count']

            elif i['modelCode'] == 17:  # 0x11
                tmp_dict['mobileD'] = i['count']
            elif i['modelCode'] == 18:  # 0x12
                tmp_dict['mobileE'] = i['count']
            elif i['modelCode'] == 19:  # 0x13
                tmp_dict['mobileF'] = i['count']
            elif i['modelCode'] == 20:  # 0x14
                tmp_dict['telecomB1'] = i['count']
            elif i['modelCode'] == 21:  # 0x15
                tmp_dict['unicomB1'] = i['count']
            elif i['modelCode'] == 22:  # 0x16
                tmp_dict['telecomB3'] = i['count']
            elif i['modelCode'] == 23:  # 0x17
                tmp_dict['unicomB3'] = i['count']

        # 统计 china_mobile
        tmp_dict['china_mobile'] = tmp_dict['mobileD'] + tmp_dict['mobileE'] + tmp_dict['mobileF'] + tmp_dict[
            'mobileE_indoor']

        # 统计 china_unicom
        tmp_dict['china_unicom'] = tmp_dict['unicomB1'] + tmp_dict['unicomB3']

        # 统计 china_telecom
        tmp_dict['china_telecom'] = tmp_dict['telecomB1'] + tmp_dict['telecomB3']

        # 统计 other_operators
        tmp_dict['other_operators'] = tmp_dict['total_count'] - \
                                      tmp_dict['china_mobile'] - \
                                      tmp_dict['china_unicom'] - \
                                      tmp_dict['china_telecom']

        # 最后将字典添加到列表中
        statistic_list.append(tmp_dict)

    return statistic_list


############################### 碰撞分析 #####################################################################
# 碰撞分析
# 参数：data_list:数据列表（列表套字典）
#       字典选项: station:站点名称,time_from:起始时间, time_end:终止时间
#       capture_interval:探针捕获IMSI号的间隔时间，单位s(默认15min，即15min中内的IMSI号不会有重复的)
# 返回：返回两个字典列表，第一个为概述信息的列表，第二个为每行的详细信息的列表
def collision_analysis(data_list):
    # 判空
    if data_list == None or data_list == []:
        return [], []
    # 循环将站点名称转换为可以查询的MAC地址
    for i in data_list:
        mac = search_mac_list_by_station(i['station'])[0]
        i['mac'] = mac  # 讲搜索结果添加到原列表中每项(字典)中去

    # 临时表名(以当前时间戳命名)
    tmp_table = 'mac' + str(int(time.time() * 100))

    # 定义列表，用于存储数据
    main_list = []  # 概述数据，列表每个元素表示可能性的IMSI号信息（降序存储）
    detail_list = []  # 详细数据，概述信息的每一行信息的详细都以列表存储在给列表中
    sqlcmd = ""

    # 统计数据，由于临时表在退出登录时会被干掉，所以只能在try-except中写逻辑
    try:
        # 链接数据库
        conn = pymysql.connect(**MYSQL_CONNECTION_CONF)
        # 游标为字典格式输出
        cur = conn.cursor(cursor=pymysql.cursors.DictCursor)

        # 先创建临时表
        sqlcmd = "create temporary table %s(imsi char(16), phone_num char(16), imsi_count int default 0, table_count int default 1, primary key(imsi));" % tmp_table
        cur.execute(sqlcmd)

        # 将所有条件的IMSI号插入到临时表中,并统计
        for i in data_list:
            # 第一遍插入是为了插入数据，并统计其符合条件数
            sqlcmd = "insert into %s(imsi, phone_num) (select distinct imsi,phone_num from imsi_%s where capture_time>='%s' and capture_time<'%s') on duplicate key update table_count=table_count+1;" \
                     % (tmp_table, i['mac'], i['time_from'], i['time_end'])
            cur.execute(sqlcmd)
            # 第二遍插入理论上是没有一条能成功的，这步就是为了计算imsi的总数（为了后面二级排序使用）
            sqlcmd = "insert into %s(imsi, phone_num) (select imsi,phone_num from imsi_%s where capture_time>='%s' and capture_time<'%s') on duplicate key update imsi_count=imsi_count+1;" \
                     % (tmp_table, i['mac'], i['time_from'], i['time_end'])
            cur.execute(sqlcmd)

        # 根据匹配数目取出数据(先取出只要有交集的数据)
        # 这里去数据是二级排序取，首先以符合条件数高的取，然后以IMSI出现次数多的再次排序
        sqlcmd = "select imsi, phone_num, table_count, imsi_count from %s where table_count>1 order by table_count desc,imsi_count desc limit 100;" % (
            tmp_table)
        cur.execute(sqlcmd)
        main_list = cur.fetchall()
        # 补全归属地等信息
        for i in main_list:
            # 补全概述列表中每张表的归属地，运营商，手机卡类型信息
            sqlcmd = "select type as operator, address from imsiaddr where phone_num='%s' limit 1;" % (i['phone_num'])
            cur.execute(sqlcmd)
            tmp_list = cur.fetchall()
            if tmp_list:
                i.update(tmp_list[0])
            # 做详细信息表数据
            tmp_detail_list = []
            for j in data_list:  # 将该IMSI号在每个条件中的数据存储到详细列表中
                sqlcmd = "select imsi,capture_time, '%s' as station, '%s' as mac, rpt_time, rssi from imsi_%s where capture_time>='%s' and capture_time<'%s' and imsi='%s' limit 500; " \
                         % (j['station'], j['mac'], j['mac'], j['time_from'], j['time_end'], i['imsi'])
                cur.execute(sqlcmd)
                tmp_list = cur.fetchall()
                if tmp_list:
                    tmp_detail_list.extend(tmp_list)
            detail_list.append(tmp_detail_list)

        # 删除临时表
        sqlcmd = "drop temporary table if exists %s;" % tmp_table
        cur.execute(sqlcmd)
        # 关闭资源
        conn.close()
        cur.close()
    except pymysql.Error:
        # 异常记录
        logging.error(sqlcmd + "\n")
        return [], []

    # 返回搜索结果
    return main_list, detail_list


############################### 伴随分析 #####################################################################
# 伴随分析
# 参数：imsi:要查询的IMSI号
#       time_from:起始时间
#       time_end:终止时间
#       capture_interval:探针捕获IMSI号的间隔时间，单位s(默认15min，即15min中内的IMSI号不会有重复的)
# 返回：返回包含可能的IMSI字典列表，根据概率降序排序
def follow_analysis(imsi, time_from, time_end, station_list=[], capture_interval=900):
    # 判断输入的关键参数存不存在，若不存在则无法搜索，直接返回空
    if (not imsi) or (not time_from) or (not time_end):
        return {}, [], []

    device_list = []  # 存储站点和MAC的列表
    sql_info=[]
    # 如果指定站点列表则将站点转成MAC地址先
    if station_list:
        for each_station in station_list:
            sqlcmd = "select site_name as station,mac from devices where site_name='%s';"%(each_station)
            res_dict_old = sqlcmd_excute(sqlcmd, 'dict')
            if res_dict_old:
                device_list+=res_dict_old
                # sql_info.append(res_dict_old)
            sqlcmd="select site_name as station,mac,sn from bcell_devices where site_name='%s';"%(each_station)
            res_dict_new = sqlcmd_excute(sqlcmd, 'dict')
            if res_dict_new:
                device_list+=res_dict_new
                # sql_info.append(res_dict_new)
    sql_info.append(device_list)
        # for each_station in station_list:

        #     res_dict = sqlcmd_excute(sqlcmd, dict)
        #     if res_dict:
        #         device_list_new.append(res_dict)
    # sql_info.append(device_list_old)
    # sql_info.append(device_list_new)
    # else:  # 若未指定站点列表，则默认所有的站点进行查询
    #     device_list = station_mac_dict_list_get()

    # 临时表名(以当前时间戳命名)
    tmp_table = 'mac' + str(int(time.time() * 100))  # 伴随信息临时表

    # 定义列表，用于存储数据
    # 目标IMSI概述信息字典
    overview_dict = {"imsi": imsi, "imsi_count": 0, "station_list": [], "phone_num": "", "operator": "", "address": ""}
    main_list = []  # 伴随IMSI号统计信息概述列表
    detail_list = []  # 伴随IMSI号详细数据
    sqlcmd = ""

    # device_list = station_mac_dict_list_get()
    # sql_info.append(device_list)
    # 统计数据，由于临时表在退出登录时会被干掉，所以只能在try-except中写逻辑
    try:
        # 链接数据库
        conn = pymysql.connect(**MYSQL_CONNECTION_CONF)
        # 游标为字典格式输出
        cur = conn.cursor(cursor=pymysql.cursors.DictCursor)

        # 创建临时表
        sqlcmd = "create temporary table %s(mac char(20), station char(64), aim_capture_time char(20), capture_time char(20), imsi char(16), rssi char(8), rpt_time char(20), phone_num char(16))default charset=utf8;" % (
            tmp_table)
        sql_info.append(sqlcmd)
        cur.execute(sqlcmd)

        # 循环将相应的数据存入临时表
        site_flag = {"val": True}  # 为了查询目标IMSI号的归属地信息使用(当第一次查到phone_num 信息时使用)
        for d in device_list:
            # 因新旧设备两个表的创建不同，以“sn”关键词界定新旧设备 ‘sn’不在d里,表明是旧设备表
            if 'sn' not in d:
                # 先将目标IMSI的数据先找到
                sqlcmd = "select capture_time,phone_num from imsi_%s where capture_time>='%s' and capture_time<'%s' and imsi='%s';" \
                         % (d['mac'], time_from, time_end, imsi)
                sql_info.append(sqlcmd)
                cur.execute(sqlcmd)
                data_list = cur.fetchall()
                if not data_list:  # 如果没有一条数据继续循环
                    continue

                # 当初次查询到目标IMSI数据时，查询更新其归属地信息
                if site_flag["val"]:
                    for data in data_list:  # 为了防止有的phone_num 字段为空
                        if data['phone_num']:
                            sqlcmd = "select phone_num, address, type as operator from imsiaddr where phone_num=%s;" % (
                                data['phone_num'])
                            sql_info.append(sqlcmd)

                            cur.execute(sqlcmd)
                            tmp_list = cur.fetchall()
                            if tmp_list:
                                overview_dict.update(tmp_list[0])
                                site_flag["val"] = False  # 初次执行成功后，把标志位取假(字典内层可以修改外层)
                                break  # 这个break是为了跳出for循环（不可少）

                # 有数据，统计下目标IMSI的数据
                overview_dict["station_list"].append(d['station'])  # 记录站点名
                overview_dict["imsi_count"] += len(data_list)  # IMSI 号和统计

                # 然后取tmp_list中每个符合记录的capture_time，以此为中心capture_interval为范围搜索，将搜索数据存入临时表中
                for i in data_list:
                    # 计算以capture_time为中心，capture_interval为范围的始终时间字符串
                    tmp_second = time.mktime(time.strptime(i['capture_time'], "%Y-%m-%d %H:%M:%S"))
                    tmp_from_second = tmp_second - capture_interval // 2
                    tmp_end_second = tmp_second + capture_interval // 2
                    tmp_from_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tmp_from_second))
                    tmp_end_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tmp_end_second))
                    # 将搜索到的数据存入临时表中
                    sqlcmd = "insert into %s(mac, station, aim_capture_time, imsi, capture_time, rssi, rpt_time, phone_num) (select distinct '%s' as mac, '%s' as station, '%s' as aim_capture_time, imsi, capture_time,rssi, rpt_time, phone_num from imsi_%s  where capture_time>='%s' and capture_time<'%s' and imsi!='%s');" \
                             % (tmp_table, d['mac'], d['station'], i['capture_time'], d['mac'], tmp_from_str, tmp_end_str,
                                imsi)
                    sql_info.append(sqlcmd)

                    cur.execute(sqlcmd)
            else:
                # 先将目标IMSI的数据先找到
                sqlcmd = "select capture_time from bcell_imsi where capture_time>='%s' and capture_time<'%s' and imsi='%s' and sn='%s';" \
                         % (time_from, time_end, imsi,d['sn'])
                sql_info.append(sqlcmd)
                cur.execute(sqlcmd)
                data_list = cur.fetchall()
                if not data_list:  # 如果没有一条数据继续循环
                    continue
                    # 有数据，统计下目标IMSI的数据
                overview_dict["station_list"].append(d['station'])  # 记录站点名
                overview_dict["imsi_count"] += len(data_list)  # IMSI 号和统计
                # 然后取tmp_list中每个符合记录的capture_time，以此为中心capture_interval为范围搜索，将搜索数据存入临时表中
                for i in data_list:
                    # 计算以capture_time为中心，capture_interval为范围的始终时间字符串
                    tmp_second = time.mktime(time.strptime(i['capture_time'], "%Y-%m-%d %H:%M:%S"))
                    tmp_from_second = tmp_second - capture_interval // 2
                    tmp_end_second = tmp_second + capture_interval // 2
                    tmp_from_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tmp_from_second))
                    tmp_end_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tmp_end_second))
                    # 将搜索到的数据存入临时表中
                    sqlcmd = "insert into %s(mac, station, aim_capture_time,imsi, capture_time, rssi, rpt_time) (select distinct '%s' as mac,'%s' as station,'%s' as aim_capture_time, imsi,capture_time,rssi,rpt_time from bcell_imsi left JOIN bcell_devices on bcell_imsi.sn=bcell_devices.sn  where capture_time>='%s' and capture_time<'%s' and imsi!='%s');" \
                             % (tmp_table, d['mac'], d['station'], i['capture_time'], tmp_from_str, tmp_end_str,
                                imsi)

                    sql_info.append(sqlcmd)

                    cur.execute(sqlcmd)


        # 统计数据
        # 按记录数据对符合的记录进行降序排序并获取数据
        sqlcmd = "select imsi,count(imsi) as imsi_count from %s group by imsi order by imsi_count desc limit 100;" % (
            tmp_table)
        cur.execute(sqlcmd)
        main_list = cur.fetchall()
        # 补全其他信息
        for i in main_list:
            # 补全主概述信息
            sqlcmd = "select phone_num, address, type as operator from imsiaddr where phone_num=(select phone_num from %s where imsi='%s' limit 1);" % (
                tmp_table, i["imsi"])
            cur.execute(sqlcmd)
            tmp_list = cur.fetchall()
            if tmp_list:
                i.update(tmp_list[0])
            # 计算下伴随IMSI号占目标IMSI号的比率
            if overview_dict["imsi_count"] and overview_dict["imsi_count"] != 0:
                i['imsi_ratio'] = round(i["imsi_count"] / overview_dict["imsi_count"], 2)  # 保留两位小数
            else:
                i['imsi_ratio'] = 0

            # 统计详细数据
            sqlcmd = "select mac, station, aim_capture_time, capture_time, rssi, rpt_time from %s where imsi='%s' limit 500;" % (
                tmp_table, i["imsi"])
            cur.execute(sqlcmd)
            tmp_list = cur.fetchall()
            if tmp_list:
                detail_list.append(tmp_list)
            else:
                detail_list.append([])

        # 删除临时表
        sqlcmd = "drop temporary table if exists %s;" % (tmp_table)
        cur.execute(sqlcmd)
        # 关闭资源
        conn.close()
        cur.close()
    except pymysql.Error:
        # 异常记录
        logging.error(sqlcmd + "\n")
        return {}, [], []

    # 返回搜索结果
    return overview_dict, main_list, detail_list


############################### 常驻人口分析 #####################################################################
# 常驻人口分析
# 参数：station:要查询的站点
#       time_from:起始时间
#       time_end:终止时间
#       capture_interval:探针捕获IMSI号的间隔时间，单位s(默认15min，即15min中内的IMSI号不会有重复的)
# 返回：返回可能的常驻人口信息，根据概率降序排序
def permanent_analysis(station, time_from, time_end, capture_interval=86400):
# def permanent_analysis(station, time_from, time_end, capture_interval=900):
    # 判断输入的关键参数存不存在，若不存在则无法搜索，直接返回空
    if (not station) or (not time_from) or (not time_end):
        return {}, []
    sql_info=[]
    # 将站点名转成MAC地址
    sqlcmd = "select site_name as station,mac from devices where site_name='%s';"%(station)
    res_dict_old=sqlcmd_excute(sqlcmd,'dict')
    sqlcmd="select site_name as station,mac,sn from bcell_devices where site_name='%s';"%(station)
    res_dict_new = sqlcmd_excute(sqlcmd, 'dict')
    device_list=res_dict_old if res_dict_old else res_dict_new

    sql_info.append(device_list[0])

    # mac = search_mac_list_by_station(station)[0]

    # 临时表名(以当前时间戳命名)
    tmp_table = 'mac' + str(int(time.time() * 100))  # 伴随信息临时表

    # 定义列表，用于存储数据
    # 目标IMSI概述信息字典
    overview_dict = {"slice_intervel": capture_interval // 60, "slice_sum": 0}
    main_list = []  # 伴随IMSI号统计信息概述列表
    sqlcmd = ""

    # 统计数据，由于临时表在退出登录时会被干掉，所以只能在try-except中写逻辑
    try:
        # 链接数据库
        conn = pymysql.connect(**MYSQL_CONNECTION_CONF)
        # 获取游标(字典游标)
        cur = conn.cursor(cursor=pymysql.cursors.DictCursor)
        # 先创建临时表，用于每个每个时间段IMSI号的信息
        sqlcmd = "create temporary table %s(imsi char(16), phone_num char(16), slice_time_from char(20), slice_time_end char(20),sn char (24))default charset=utf8;" % (
            tmp_table)
        sql_info.append(sqlcmd)
        cur.execute(sqlcmd)
        if "sn" not in device_list[0]:
            # 计算开始、结束时间转出的时间戳
            from_seconds = time.mktime(time.strptime(time_from, "%Y-%m-%d %H:%M:%S"))
            end_seconds = time.mktime(time.strptime(time_end, "%Y-%m-%d %H:%M:%S"))

            # 以捕获间隔为周期，循环将每次查询到的IMSI号和数量插入到IMSI临时表中
            while from_seconds < end_seconds:
                # 计算截止端时间戳值
                limit_seconds = from_seconds + capture_interval
                if limit_seconds > end_seconds:  # 如果超出终止时间范围则按终止时间值算
                    limit_seconds = end_seconds
                from_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(from_seconds))
                end_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(limit_seconds))
                # 将每个时间段的IMSI号去重存入临时表
                sqlcmd = "insert into %s(imsi, phone_num, slice_time_from, slice_time_end) (select distinct imsi,phone_num,'%s' as time_slice_from, '%s' as time_slice_end from imsi_%s where capture_time>='%s' and capture_time<='%s');" \
                         % (tmp_table, from_str, end_str, device_list[0]['mac'], from_str, end_str)
                sql_info.append(sqlcmd)

                cur.execute(sqlcmd)
                # 起始时间戳更新，必须做
                from_seconds = limit_seconds
                overview_dict["slice_sum"] += 1  # 切片数据量加一
        else:
            # 计算开始、结束时间转出的时间戳
            from_seconds = time.mktime(time.strptime(time_from, "%Y-%m-%d %H:%M:%S"))
            end_seconds = time.mktime(time.strptime(time_end, "%Y-%m-%d %H:%M:%S"))

            # 以捕获间隔为周期，循环将每次查询到的IMSI号和数量插入到IMSI临时表中
            while from_seconds < end_seconds:
                # 计算截止端时间戳值
                limit_seconds = from_seconds + capture_interval
                if limit_seconds > end_seconds:  # 如果超出终止时间范围则按终止时间值算
                    limit_seconds = end_seconds
                from_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(from_seconds))
                end_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(limit_seconds))
                # 将每个时间段的IMSI号去重存入临时表
                sqlcmd = "insert into %s(imsi, slice_time_from, slice_time_end,sn) (select distinct imsi,'%s' as time_slice_from, '%s' as time_slice_end ,'%s' as sn from bcell_imsi where sn='%s' and capture_time>='%s' and capture_time<='%s');" \
                         % (tmp_table, from_str, end_str, device_list[0]['sn'],device_list[0]['sn'], from_str, end_str)
                sql_info.append(sqlcmd)

                cur.execute(sqlcmd)
                # 起始时间戳更新，必须做
                from_seconds = limit_seconds
                overview_dict["slice_sum"] += 1  # 切片数据量加一
        # 取出临时表中数据
        sqlcmd = "select imsi,count(imsi) as time_count from %s group by imsi having time_count>'%d' order by time_count desc limit 500;" % (
        tmp_table, overview_dict["slice_sum"] // 3)
        sql_info.append(sqlcmd)

        cur.execute(sqlcmd)
        main_list = cur.fetchall()
        # 补全其他信息
        # for i in main_list:
        #     # 补全归属地信息
        #     sqlcmd = "select phone_num, address, type as operator from imsiaddr where phone_num=(select phone_num from %s where phone_num is not null and phone_num!='' and imsi='%s' limit 1);" % (
        #
        #     tmp_table, i["imsi"])
        #     sql_info.append(sqlcmd)
        #
        #     cur.execute(sqlcmd)
        #     tmp_list = cur.fetchall()
        #     if tmp_list:
        #         i.update(tmp_list[0])
        #     else:  # 必须得有，否则前端会显示有问题
        #         i.update({"phone_num": "", "address": "", "operator": ""})
        #     # 补全IMSI总和信息
        #     sqlcmd = "select count(1) as imsi_count from imsi_%s where imsi='%s';" % (device_list['mac'], i['imsi'])
        #     sql_info.append(sqlcmd)
        #
        #     cur.execute(sqlcmd)
        #     tmp_list = cur.fetchall()
        #     if tmp_list:
        #         i.update(tmp_list[0])
        #     else:  # 必须得有，否则前端会显示有问题
        #         i.update("imsi_count")

        # 删除临时表
        sqlcmd = "drop temporary table if exists %s;" % (tmp_table)
        cur.execute(sqlcmd)
        # 关闭资源
        conn.close()
        cur.close()
    except pymysql.Error:
        # 异常记录
        logging.error(sqlcmd + "\n")

    # 返回搜索结果
    return overview_dict, main_list,sql_info


############################## 站点数据查询 ##############################################################
# 站点地图查询IMSI数据
# 参数：site_name:站点名称
#       from_time:起始捕获时间
#       end_time:终止捕获时间
#       start_index:分页起始页
#       request_count:请求数据量
def site_map_query(site_name, from_time, end_time, start_index=0, request_count=500):
    # 创建一个返回结构对象
    ret_dict = ResDataDict()

    # 先将站点名转为MAC地址
    mac = search_mac_by_station(site_name)
    if not mac:
        ret_dict.setStatus(-1, "站点 %s 不存在！" % (site_name))
        return ret_dict

    sqlcmd = ""
    try:
        # 链接数据库
        conn = pymysql.connect(**MYSQL_CONNECTION_CONF)
        # 游标设置为列表类型
        cur = conn.cursor(cursor=pymysql.cursors.DictCursor)
        # 查询数据记录总数
        sqlcmd = "select count(1) from imsi_%s where capture_time>='%s' and capture_time<'%s';" \
                 % (mac, from_time, end_time)
        cur.execute(sqlcmd)
        tmp_list = cur.fetchall()
        if tmp_list:
            ret_dict.setSum(int(tmp_list[0]["count(1)"]))
        # 查询数据
        sqlcmd = "select capture_time,rssi,imsi from imsi_%s where capture_time>='%s' and capture_time<'%s' limit %s,%s;" \
                 % (mac, from_time, end_time, start_index, request_count)
        cur.execute(sqlcmd)
        # 获取搜索结果
        tmp_list = cur.fetchall()
        if tmp_list:
            ret_dict.setData(tmp_list)
        # 关闭资源
        conn.close()
        cur.close()
        ret_dict.setStatus(1, "查询成功")
    except pymysql.Error:
        # 异常记录
        logger.error(sqlcmd + "\n")
        ret_dict.setStatus(-1, "数据库查询失败！")

    # 返回搜索结果
    return ret_dict