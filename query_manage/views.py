from django.shortcuts import render, HttpResponse, redirect
from django.http import StreamingHttpResponse
from query_manage import models
import json
import time
import pandas as pd
from query_manage.utils import PageHelper, ExcelHelper, FileUtils
from django.contrib.auth.decorators import login_required, REDIRECT_FIELD_NAME
from prober_manage.settings import LOCAL_FILE_PATH, ENGINEERING_PATTERN, logger
from devices_manage.views import add_action_log
from wifi_prober_manage.data_analysis import MyExcel
from query_manage.utils.DataFormat import ResDataDict
from utils.models import get_sqlalchemy_engine
from nbfunc.nb_query import search_middleware


# 业务逻辑界面

# 查询界面入口
@login_required(None, REDIRECT_FIELD_NAME, "/users/login/")
def query_home(request):
    if request.method == "GET":
        # 获取设备站点信息列表
        stat_list = models.station_list_get()

        return render(request, "query_manage/query.html", {"station_list": stat_list})


# 查询功能ajax请求
def query_search(request):
    start_time = time.time()
    if request.method == 'POST':
        # 获取信息
        addr_data = ''.join((request.POST.get("province"),
                             request.POST.get("city"),
                             request.POST.get("area")))
        stat_data = str(request.POST.get("station"))
        mac_data = str(request.POST.get("MAC_input")).upper().strip()
        time_from_data = str(request.POST.get("time_from"))
        time_end_data = str(request.POST.get("time_end"))
        imsi_data = str(request.POST.get("IMSI_input").strip())
        orderby_data = request.POST.get("orderby", None)
        orderdir_data = request.POST.get("orderdir", "asc")
        page_num = int(request.POST.get("page", 1))

        # 根据用户输入获取IMSI列表
        imsi_list = []
        if imsi_data:  # 一定要加判断否则，''.splite(',') 结果为 [''] 不为空哦！
            imsi_list = list(set(imsi_data.strip().split(',')))  # 使用set作为中转的目的为了去重

        # 获取MAC地址列表
        mac_list = []
        if mac_data:  # 判断用户是否输入了MAC,若输入以输入为主
            if models.table_isexist(mac_data):  # 判断MAC地址是否存在
                mac_list.append(mac_data)
        else:
            mac_list = models.search_mac_list_by_station(stat_data, addr_data)

        # 执行nb功能操作
        search_middleware(mac_list, imsi_list, time_from_data, time_end_data)

        # 获取总记录数目
        total_records = models.get_count_by_search(
            mac_list=mac_list,
            imsi_list=imsi_list,
            time_from=time_from_data,
            time_end=time_end_data
        )
        # 如果搜索不到数据则返回
        if total_records == 0:
            return HttpResponse(json.dumps({"data": [], "page": ""}))

        # 根据MAC地址以及其他数据进行搜索
        info_list = models.get_data_by_search(
            pagefrom=page_num,
            mac_list=mac_list,
            imsi_list=imsi_list,
            time_from=time_from_data,
            time_end=time_end_data,
            orderby=orderby_data,
            orderdir=orderdir_data,
        )
        # 获取页面的记录数据
        page_obj = PageHelper.PageHelper(total_records, page_num)
        page_str = page_obj.pageStr()

        # 添加日志记录
        stop_time = time.time()
        logger.info("详细搜索{查询地址:%s 站点名称:%s 时间:%s到%s MAC:%s IMSI列表:%s 当前%d页} 耗时:%ss"
                    % (addr_data, stat_data, time_from_data, time_end_data, mac_data, imsi_list, page_num,
                       stop_time - start_time))

        # 整合数据并返回
        data_dict = {"data": info_list, "page": page_str}
        return HttpResponse(json.dumps(data_dict))


# 测试数据导出post请求
def test_export(request):
    start_time = time.time()
    if request.method == 'POST':
        addr_data = ''.join((str(request.POST.get("province", "")),
                             str(request.POST.get("city", "")),
                             str(request.POST.get("area", ""))))
        stat_data = str(request.POST.get("station", ""))
        mac_data = str(request.POST.get("MAC_input", "")).upper().strip()
        time_from_data = str(request.POST.get("time_from", ""))
        time_end_data = str(request.POST.get("time_end", ""))
        imsi_data = request.POST.get('IMSI_input')

        # 根据用户输入获取IMSI列表
        imsi_list = []
        if imsi_data:  # 一定要加判断否则，''.splite(',') 结果为 [''] 不为空哦！
            imsi_list = list(set(imsi_data.strip().split(',')))  # 使用set作为中转的目的为了去重
        else:
            return redirect("/query_manage/query/")

        # 获取统计数据信息列表
        info_list = models.get_test_export_data(
            mac=mac_data,
            station=stat_data,
            imsi_list=imsi_list,
            time_from=time_from_data,
            time_end=time_end_data,
            addr=addr_data,
        )
        # 如果没数据直接跳转返回
        if not info_list:
            return redirect("/query_manage/query/")

        # 显示在弹出对话框中的默认的下载文件名
        if stat_data:  # 以站点名进行的查询
            show_filename = ''.join((stat_data, " ", str(request.user.username), " ",
                                     time.strftime("%Y-%m-%d %H-%M-%S", time.localtime()), " test.xlsx"))
        else:  # 以MAC进行的查询
            show_filename = ''.join((mac_data, " ", str(request.user.username), " ",
                                     time.strftime("%Y-%m-%d %H-%M-%S", time.localtime()), " test.xlsx"))
        # 要下载的文件路径
        save_filename = ''.join((LOCAL_FILE_PATH['detailed_query_excel'], show_filename))
        # sheet名
        sheet_name = "sheet1"

        nt = ExcelHelper.TestResultExcel(sheet_name)
        # 修改表头信息
        nt.alter_header(0, ''.join(("IMSI(", time_from_data, " ", time_end_data, ")")))
        # 遍历返回数据列表，组合成excel输出的每个表项(因为有些数据excel不想要,但为了后期扩展故保留)
        for i in info_list:
            tmp_list = []
            # 文档模块名称: IMSI", "移动D", "移动E", "移动F", "移动", "电信B1", "电信B3", "电信", "联通（B3）", "总计"
            tmp_list.append(i['imsi'])
            tmp_list.append(i['mobileD'])
            tmp_list.append(i['mobileE'] + i['mobileE_indoor'])
            tmp_list.append(i['mobileF'])
            tmp_list.append(i['telecomB1'])
            tmp_list.append(i['telecomB3'])
            tmp_list.append(i['unicomB3'])
            nt.write_a_row(tmp_list)  # 将数据写入excel模块
        nt.save(save_filename)  # 保存数据到文档

        # 增加日志记录
        add_action_log(request.user.username, "查询数据导出", "文件路径:%s" % (save_filename))
        stop_time = time.time()
        logger.info("查询数据导出{文件路径:%s} 耗时:%ss" % (save_filename, stop_time - start_time))

        # 返回数据
        response = StreamingHttpResponse(FileUtils.file_read(save_filename, "rb"))  # 要下载的文件路径
        response['Content-Type'] = 'application/vnd.ms-excel;charset=utf-8'
        response['Content-Disposition'] = "attachment; filename=" + show_filename.encode("utf-8").decode(
            "ISO - 8859 - 1") + ";"
        return response

    return redirect("/query_manage/query/")


# 搜索数据导出post请求
def search_export(request):
    start_time = time.time()
    if request.method == 'POST':
        addr_data = ''.join((str(request.POST.get("province", "")),
                             str(request.POST.get("city", "")),
                             str(request.POST.get("area", ""))))
        stat_data = str(request.POST.get("station", ""))
        mac_data = str(request.POST.get("MAC_input", "")).upper().strip()
        time_from_data = str(request.POST.get("time_from", ""))
        time_end_data = str(request.POST.get("time_end", ""))
        imsi_data = request.POST.get('IMSI_input')

        # 根据用户输入获取IMSI列表
        imsi_list = []
        if imsi_data:  # 一定要加判断否则，''.splite(',') 结果为 [''] 不为空哦！
            imsi_list = list(set(imsi_data.strip().split(',')))  # 使用set作为中转的目的为了去重

        # 获取MAC地址列表
        mac_list = []
        if mac_data:  # 判断用户是否输入了MAC,若输入以输入为主
            if models.table_isexist(mac_data):  # 判断MAC地址是否存在
                mac_list.append(mac_data)
        else:
            mac_list = models.search_mac_list_by_station(stat_data, addr_data)

        # 显示在弹出对话框中的默认的下载文件名
        if stat_data:  # 以站点名进行的查询
            show_filename = ''.join((stat_data, " ", str(request.user.username), " ",
                                     time.strftime("%Y-%m-%d %H-%M-%S", time.localtime()), " query.xlsx"))
        else:  # 以MAC进行的查询
            show_filename = ''.join((mac_data, " ", str(request.user.username), " ",
                                     time.strftime("%Y-%m-%d %H-%M-%S", time.localtime()), " query.xlsx"))
        # 要下载的文件路径
        save_filename = ''.join((LOCAL_FILE_PATH['detailed_query_excel'], show_filename))

        search_middleware(mac_list, imsi_list, time_from_data, time_end_data)
        # 获取统计数据信息列表
        sql_cmd = models.get_search_export_sqlcmd(
            mac_list=mac_list,
            imsi_list=imsi_list,
            time_from=time_from_data,
            time_end=time_end_data
        )

        # 读取搜索数据和到dataframe，合并，写入表格
        engine = get_sqlalchemy_engine('4g')
        df_sr = pd.read_sql(sql_cmd, engine)
        sql_cmd = "SELECT name,imsi,department,phone_num,operator FROM imsi_black_list_qhd20190321;"
        df_cl = pd.read_sql(sql_cmd, engine).drop_duplicates()
        df = pd.merge(df_sr, df_cl, how='left')
        df.columns = ['捕获时间', 'IMSI', 'IMEI', '信号强度', '姓名', '部门', '手机号', '运营商']
        s_count = df['手机号'].value_counts()
        imsi_count_dic = {'手机号': s_count.index, '频次': s_count.values}
        df_counts = pd.merge(df.drop_duplicates(['IMSI']), pd.DataFrame(imsi_count_dic))

        excel = pd.ExcelWriter(save_filename)
        df.to_excel(excel, "全部采集记录")
        df_counts.to_excel(excel, index=False, sheet_name="名单内统计")
        excel.save()

        # 增加日志记录
        add_action_log(request.user.username, "查询数据导出", "文件路径:%s" % save_filename)
        stop_time = time.time()
        logger.info("查询数据导出{文件路径:%s} 耗时:%ss" % (save_filename, stop_time - start_time))

        # 返回数据
        response = StreamingHttpResponse(FileUtils.file_read(save_filename, "rb"))  # 要下载的文件路径
        response['Content-Type'] = 'application/vnd.ms-excel;charset=utf-8'
        response['Content-Disposition'] = "attachment; filename=" + show_filename.encode("utf-8"). \
            decode("ISO - 8859 - 1") + ";"
        return response

    return redirect("/query_manage/query/")


# 轨迹分析
@login_required(None, REDIRECT_FIELD_NAME, "/users/login/")
def query_map(request, map_type):
    logger.debug(map_type)
    context = {
        'map_type': map_type,
        'map_type_json': json.dumps(map_type),
    }
    return render(request, "query_manage/query_map.html", context)


# 轨迹分析ajax请求
def query_map_search(request):
    start_time = time.time()
    if request.method == 'POST':
        # 获取信息
        time_from_data = str(request.POST.get("time_from"))
        time_end_data = str(request.POST.get("time_end"))
        imsi_data = str(request.POST.get("IMSI_input").strip())
        page_num = int(request.POST.get("page", 1))

        # 根据用户输入获取IMSI列表
        if not imsi_data:  # 一定要加判断否则，''.splite(',') 结果为 [''] 不为空哦！
            return HttpResponse(json.dumps({"data": "", "page": "", "device": ""}))

        # 获取整体信息
        station_list, info_list, total_records = models.get_datas_by_map_search(
            pagefrom=page_num,
            imsi=imsi_data,
            time_from=time_from_data,
            time_end=time_end_data,
        )

        # 如果搜索不到数据则返回
        if total_records == 0:
            return HttpResponse(json.dumps({"data": "", "page": "", "device": ""}))

        # 获取页面的记录数据
        page_obj = PageHelper.PageHelper(total_records, page_num)
        page_str = page_obj.pageStr()

        # 添加日志记录
        stop_time = time.time()
        logger.info(" 轨迹分析:{ imsi:%s 时间:%s到%s 当前%d页} 耗时:%s s"
                    % (imsi_data, time_from_data, time_end_data, page_num, stop_time - start_time))

        # 整合数据并返回
        return HttpResponse(json.dumps({"data": info_list, "page": page_str, "device": station_list}))


# 轨迹分析ajax请求 +新设备
def query_map_search_new(request):
    start_time = time.time()
    if request.method == 'POST':
        # 页面显示数限制
        recordsLimt = 30
        # # 获取信息
        time_from_data = str(request.POST.get("time_from"))
        time_end_data = str(request.POST.get("time_end"))
        imsi_data = str(request.POST.get("IMSI_input").strip())
        page_num = int(request.POST.get("page", 1))
        #
        # 根据用户输入获取IMSI列表
        if not imsi_data:  # 一定要加判断否则，''.splite(',') 结果为 [''] 不为空哦！
            return HttpResponse(json.dumps({"data": "", "page": "", "device": ""}))

        # 获取整体信息
        station_list, info_list, total_records=[],[],0
        station_list_new, info_list_new, total_records_new = [], [], 0

        # 新老设备整合   先查老设备再查新设备，可更改顺序
        station_list, info_list, total_records = models.get_datas_by_map_search(imsi_data, time_from_data,
                                                                                time_end_data, pagefrom=page_num)
        if len(info_list) < recordsLimt:
            station_list_new, info_list_new, total_records_new = models.get_datas_by_map_search_new(imsi_data,
                                                                                                         time_from_data,
                                                                                                         time_end_data,
                                                                                                         pagefrom=page_num,
                                                                                                         recordsLimt=recordsLimt - len(
                                                                                                             info_list))
            station_list += station_list_new
            info_list += info_list_new
            total_records += total_records_new

        # 如果搜索不到数据则返回
        if total_records == 0:
            return HttpResponse(json.dumps({"data": "", "page": "", "device": ""}))

        # 获取页面的记录数据
        page_obj = PageHelper.PageHelper(total_records_new, page_num)
        page_str = page_obj.pageStr()

        # 添加日志记录
        stop_time = time.time()
        logger.info(" 轨迹分析:{ imsi:%s 时间:%s到%s 当前%d页} 耗时:%s s"
                    % (imsi_data, time_from_data, time_end_data, page_num, stop_time-start_time))

        # 整合数据并返回
        return HttpResponse(json.dumps({"device": station_list, "data": info_list, "page": page_str}))


# 统计分析界面
@login_required(None, REDIRECT_FIELD_NAME, "/users/login/")
def query_statistics(request):
    if request.method == "GET":
        # 获取设备站点信息列表
        stat_list = models.station_list_get()
        return render(request, "query_manage/query_statistics.html", {"station_list": stat_list})


# 统计分析ajax请求入口
def query_statistics_search(request):
    start_time = time.time()
    if request.method == 'POST':
        # 获取信息
        gran_cycle = str(request.POST.get("gran_cycle")).strip().lower()
        stat_data = str(request.POST.get("station"))
        time_from_data = str(request.POST.get("time_from"))
        time_end_data = str(request.POST.get("time_end"))

        # 先通过站点找到MAC地址信息
        if not stat_data:
            return HttpResponse(json.dumps({"data": ""}))

        mac_data = models.search_mac_list_by_station(stat_data)[0]

        # 根据用户输入的统计粒度进行计算
        info_list = models.statistics_by_search(gran_cycle=gran_cycle,
                                                mac=mac_data,
                                                time_from=time_from_data,
                                                time_end=time_end_data
                                                )

        # 添加日志记录
        stop_time = time.time()
        logger.info("统计分析:{ 统计方式:%s 站点:%s(%s) 时间:%s到%s} 耗时:%s s"
                    % (gran_cycle, stat_data, mac_data, time_from_data, time_end_data, stop_time - start_time))

        if info_list:
            return HttpResponse(json.dumps({"data": info_list}))

    return HttpResponse(json.dumps({"data": ""}))


# 碰撞分析界面
@login_required(None, REDIRECT_FIELD_NAME, "/users/login/")
def collision_analysis(request):
    if request.method == "GET":
        # 获取设备站点信息列表
        stat_list = models.station_list_get()

        return render(request, "query_manage/collision_analysis.html", {"station_list": stat_list})


# 碰撞分析ajax请求
def collision_analysis_search(request):
    start_time = time.time()
    if request.method == "POST":
        # 获取请求数据json字符串
        data_json = request.POST.get("data_list")

        # 将json字符串转出对象
        data_list = json.loads(data_json)  # 返回数据为一个列表套字典结构，列表中每个元素为一个请求条件
        # 获取碰撞分析数据
        main_list, detail_list = models.collision_analysis(data_list)

        # 添加日志记录
        stop_time = time.time()
        logger.info("碰撞分析:{ 条件:%s } 耗时:%s s" % (data_list, stop_time - start_time))
        add_action_log(request.user.username, "碰撞分析", "耗时:%s s" % (stop_time - start_time))

        # 如果查询有数据就返回
        if main_list:
            return HttpResponse(json.dumps({"main": main_list, "detail": detail_list}))

    return HttpResponse(json.dumps({"main": [], "detail": []}))


# 伴随分析界面
@login_required(None, REDIRECT_FIELD_NAME, "/users/login/")
def follow_analysis(request):
    # 获取设备站点信息列表
    stat_list = models.station_list_get()
    stat_list+=models.station_list_get_new()
    return render(request, "query_manage/follow_analysis.html", {"station_list": stat_list})


# 伴随分析ajax请求 +新设备 new
def follow_analysis_search(request):
    start_time = time.time()
    if request.method == 'POST':
        # 获取信息
        station_data = str(request.POST.get("station_list")).strip()
        station_list = json.loads(station_data)
        imsi_data = str(request.POST.get("IMSI_input")).strip()
        time_from_data = str(request.POST.get("time_from"))
        time_end_data = str(request.POST.get("time_end"))

        overview_dict, main_list, detail_list = models.follow_analysis(
            imsi=imsi_data,
            time_from=time_from_data,
            time_end=time_end_data,
            station_list=station_list,
        )

        # 添加日志记录
        stop_time = time.time()
        logger.info("伴随分析:{ IMSI:%s(%s - %s) } 耗时:%s s"
                    % (imsi_data, time_from_data, time_end_data, stop_time - start_time))

        # return HttpResponse(json.dumps({"overview": overview_dict, "main": main_list, "detail": detail_list,"sql_info":sql_info}))
        # # 如果查询有数据就返回
        if main_list:
            return HttpResponse(json.dumps({"overview": overview_dict, "main": main_list, "detail": detail_list}))

    return HttpResponse(json.dumps({"overview": {}, "main": [], "detail": []}))


# 常驻人口分析
@login_required(None, REDIRECT_FIELD_NAME, "/users/login/")
def permanent_analysis(request):
    if request.method == "GET":
        # 获取设备站点信息列表
        stat_list = models.station_list_get()
        stat_list+=models.station_list_get_new()
        return render(request, "query_manage/permanent_analysis.html", {"station_list": stat_list})


# 常驻人口ajax请求
def permanent_analysis_search(request):
    start_time = time.time()
    if request.method == 'POST':
        # 获取信息
        stat_data = str(request.POST.get("station"))
        time_from_data = str(request.POST.get("time_from"))
        time_end_data = str(request.POST.get("time_end"))

        # 获取常驻人口数据
        overview_dict, main_list ,sql_info= models.permanent_analysis(
            station=stat_data,
            time_from=time_from_data,
            time_end=time_end_data
        )

        # 添加日志记录
        stop_time = time.time()
        logger.info("常驻人口分析:{ 站点:%s 从%s到%s } 耗时:%s s"
                    % (stat_data, time_from_data, time_end_data, stop_time - start_time))

        # 返回查询数据
        return HttpResponse(json.dumps({"overview": overview_dict, "main": main_list,"sql_info":sql_info}))

    return HttpResponse(json.dumps({"overview": {}, "main": []}))


# 站点地图数据查询
def site_map_query(request):
    start_time = time.time()
    if request.method == "POST":
        logger.debug(request.POST)
        start_index = request.POST.get("start_index")
        site_name = request.POST.get("query_sitename")
        from_time = request.POST.get("query_start_time")
        end_time = request.POST.get("query_end_time")
        request_count = request.POST.get("request_count")

        ret_dict = models.site_map_query(site_name=site_name,
                                         from_time=from_time,
                                         end_time=end_time,
                                         start_index=start_index,
                                         request_count=request_count
                                         )

        # 添加日志记录
        stop_time = time.time()
        logger.info("地图站点查询:{ 站点:%s 从%s到%s } 耗时:%s s"
                    % (site_name, from_time, end_time, stop_time - start_time))

        # 返回查询数据
        return HttpResponse(ret_dict)