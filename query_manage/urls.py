from django.conf.urls import url
from . import views
from django.http import HttpRequest
# 路由分配，
# 本模块下的路由均已 http:xxx.xxx.xx.x/query_manage/  开头
# query/ 主要为模块主路由，GET请求页面时走这里
# query/search/ 主要用于查询设备信息使用，请求为 AJAX 的 POST 请求

from django.http import HttpResponse
urlpatterns = [
    url(r'^xuhu/$', lambda request:HttpResponse("hello world")),
    # 详细查询
    url(r'^query/$', views.query_home, name='query'),
    url(r'^query/search/$', views.query_search, name='search'),
    url(r'^query/test_export/$', views.test_export, name='test_export'),
    url(r'^query/search_export/$', views.search_export, name='search_export'),
    # 轨迹分析
    url(r'^query_map/(?P<map_type>\w+)/$', views.query_map, name='query_map'),
    # ***新旧设备整合***
    url(r'^query_map/online/search_new/$', views.query_map_search_new),
    url(r'^query_map/offline/search_new/$', views.query_map_search_new),
    #***旧设备***
    # url(r'^query_map/online/search/$', views.query_map_search),
    # url(r'^query_map/offline/search/$', views.query_map_search),

    # 查询统计
    url(r'^query_statistics/$', views.query_statistics, name='query_statistics'),
    url(r'^query_statistics/search/$', views.query_statistics_search, name='statistics_search'),
    # 碰撞分析
    url(r'^collision_analysis/$', views.collision_analysis, name='collision_analysis'),
    url(r'^collision_analysis/search/$', views.collision_analysis_search, name='collision_search'),
    # 伴随分析
    url(r'^follow_analysis/$', views.follow_analysis, name='follow_analysis'),
    url(r'^follow_analysis/search/$', views.follow_analysis_search, name='follow_search'),
    # 常驻人口分析
    url(r'^permanent_analysis/$', views.permanent_analysis, name='permanent_analysis'),
    url(r'^permanent_analysis/search/$', views.permanent_analysis_search, name='permanent_search'),

    # 设备中心站点地图查询请求
    url(r'^query/site_map_query$', views.site_map_query, name='site_map_query'),

]