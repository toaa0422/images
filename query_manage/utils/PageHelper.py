# 该模块主要用于解决html分页的实现问题


class PageHelper:
    # 构造函数，
    # 参数：totalRecords:总记录数,
    # currentPage:当前显示页数（高亮）,
    # recordsPerPage:每页应该显示记录数目，便于计算页码数使用,
    # pageNumber:最大显示页数（显示数字的a标签的个数）（最好是奇数，否则有点小问题）
    def __init__(self, totalRecords, currentPage, recordsPerPage=30, pageNumber=11):
        self.totalRecord = totalRecords
        self.curPage = currentPage
        self.perPage = recordsPerPage
        self.maxPage = pageNumber

    # 返回记录折算总共页数
    def totalPage(self):
        div, remain = divmod(self.totalRecord, self.perPage)
        if remain != 0:
            div += 1
        return div

    # 返回页面HTML语言字符串
    def pageStr(self):
        total_page = self.totalPage()       # 获取这么多记录转化成的页码数
        # 如果总页数为空直接返回空字符串
        if total_page <= 0:
            return ""

        page_list = []

        # 添加首页标签
        if total_page > self.maxPage:      # 只有需要显示的页数超过了能显示的最大页数才需要首页
            page_list.append('<li><a onclick="searchSubmit(1)" style="cursor: pointer">首页</a></li>')

        # 如果当前页为起始页则点击上一页时不变化
        if self.curPage == 1:
            page_list.append('<li><a style="cursor: pointer">上一页</a></li>')
        else:
            page_list.append('<li><a onclick="searchSubmit(%d)" style="cursor: pointer">上一页</a></li>' % (self.curPage - 1))

        # 判断总页数是否达到最大显示页数
        if total_page <= self.maxPage:
            page_range_start = 1                #page_range 包头不包为尾
            page_range_end = total_page + 1
        else:
            # 若果显示的页数到中部，则计算时按当前页为中间计算
            if self.curPage <= self.maxPage:
                page_range_start = 1
                page_range_end = self.maxPage + 1
            else:
                page_range_start = self.curPage - self.maxPage // 2
                page_range_end = self.curPage + self.maxPage // 2 + 1
                if page_range_end > total_page:    #最后的显示倒着来显示
                    page_range_start = total_page - self.maxPage
                    page_range_end = total_page + 1

        # 遍历添加形成HTML代码
        for i in range(page_range_start, page_range_end):
            if i == self.curPage:		# 当前页高亮现实
                page_list.append('<li class="active"><a onclick="searchSubmit(%d)" style="cursor: pointer">%d</a></li>' % (i, i))
            else:
                page_list.append('<li><a onclick="searchSubmit(%d)" style="cursor: pointer">%d</a></li>' % (i, i))

        # 如果当前页为末尾页则点击下一页时不变化
        if self.curPage == total_page:
            page_list.append('<li><a>下一页</a></li>')
        else:
            page_list.append('<li><a onclick="searchSubmit(%d)" style="cursor: pointer">下一页</a></li>' % (self.curPage + 1))

        # 添加尾页标签
        if total_page > self.maxPage:  # 只有需要显示的页数超过了能显示的最大页数才需要首页
            page_list.append('<li><a onclick="searchSubmit(%d)" style="cursor: pointer">尾页</a></li>' %(total_page))

        pager = "".join(page_list)
        return pager


if __name__ == '__main__':
    page_obj = PageHelper(10000, 12)
    page_str = page_obj.pageStr()
    print(page_str)


