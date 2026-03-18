"""
旺店通开放平台API客户端
文档: https://open.wangdian.cn
"""
import hashlib
import time
import json
import requests
from backend.config.settings import WDT_API


class WDTClient:
    """旺店通API客户端"""

    def __init__(self):
        self.base_url = WDT_API['base_url']
        self.sid = WDT_API['sid']
        self.appkey = WDT_API['appkey']
        self.appsecret = WDT_API['appsecret']

    def _sign(self, params: dict) -> str:
        """生成签名
        签名规则: MD5(appsecret + 排序拼接的key=value + appsecret)
        """
        sorted_params = sorted(params.items(), key=lambda x: x[0])
        sign_str = self.appsecret
        for key, value in sorted_params:
            sign_str += f"{key}{value}"
        sign_str += self.appsecret
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()

    def _request(self, method: str, params: dict = None) -> dict:
        """发起API请求"""
        if params is None:
            params = {}

        # 公共参数
        params.update({
            'sid': self.sid,
            'appkey': self.appkey,
            'timestamp': str(int(time.time())),
        })

        # 生成签名
        params['sign'] = self._sign(params)

        url = f"{self.base_url}/{method}"

        try:
            response = requests.post(url, data=params, timeout=30)
            response.raise_for_status()
            result = response.json()

            if result.get('code') != 0:
                raise Exception(f"旺店通API错误: {result.get('message', '未知错误')}, code={result.get('code')}")

            return result
        except requests.RequestException as e:
            raise Exception(f"旺店通API请求失败: {str(e)}")

    # ==================== 库存相关接口 ====================

    def get_stock_query(self, page_no=0, page_size=100, **kwargs) -> dict:
        """查询库存
        接口: stockquery.queryStockSpec
        """
        params = {
            'page_no': str(page_no),
            'page_size': str(page_size),
        }
        params.update(kwargs)
        return self._request('stockquery.queryStockSpec', params)

    def get_stock_summary(self) -> dict:
        """获取库存汇总"""
        return self._request('stockquery.queryStockSummary')

    # ==================== 销售相关接口 ====================

    def get_trade_query(self, start_time: str, end_time: str,
                        page_no=0, page_size=100, **kwargs) -> dict:
        """查询销售订单
        接口: trade.queryTrades
        """
        params = {
            'start_time': start_time,
            'end_time': end_time,
            'page_no': str(page_no),
            'page_size': str(page_size),
        }
        params.update(kwargs)
        return self._request('trade.queryTrades', params)

    def get_sales_stats(self, start_time: str, end_time: str, **kwargs) -> dict:
        """查询销售统计
        接口: stockquery.querySalesStat
        """
        params = {
            'start_time': start_time,
            'end_time': end_time,
        }
        params.update(kwargs)
        return self._request('stockquery.querySalesStat', params)

    # ==================== 采购相关接口 ====================

    def get_purchase_orders(self, start_time: str, end_time: str,
                           page_no=0, page_size=100, **kwargs) -> dict:
        """查询采购订单
        接口: purchase.queryPurchaseOrders
        """
        params = {
            'start_time': start_time,
            'end_time': end_time,
            'page_no': str(page_no),
            'page_size': str(page_size),
        }
        params.update(kwargs)
        return self._request('purchase.queryPurchaseOrders', params)

    def get_purchase_return(self, start_time: str, end_time: str,
                           page_no=0, page_size=100, **kwargs) -> dict:
        """查询采购退货单"""
        params = {
            'start_time': start_time,
            'end_time': end_time,
            'page_no': str(page_no),
            'page_size': str(page_size),
        }
        params.update(kwargs)
        return self._request('purchase.queryPurchaseReturns', params)

    # ==================== 商品相关接口 ====================

    def get_goods_query(self, page_no=0, page_size=100, **kwargs) -> dict:
        """查询商品信息
        接口: goods.queryGoods
        """
        params = {
            'page_no': str(page_no),
            'page_size': str(page_size),
        }
        params.update(kwargs)
        return self._request('goods.queryGoods', params)

    def get_goods_spec(self, page_no=0, page_size=100, **kwargs) -> dict:
        """查询商品规格(SKU)
        接口: goods.queryGoodsSpec
        """
        params = {
            'page_no': str(page_no),
            'page_size': str(page_size),
        }
        params.update(kwargs)
        return self._request('goods.queryGoodsSpec', params)

    # ==================== 供应商相关接口 ====================

    def get_suppliers(self, page_no=0, page_size=100, **kwargs) -> dict:
        """查询供应商列表"""
        params = {
            'page_no': str(page_no),
            'page_size': str(page_size),
        }
        params.update(kwargs)
        return self._request('supplier.querySuppliers', params)

    # ==================== 批量获取工具方法 ====================

    def fetch_all_pages(self, method_func, page_size=100, **kwargs) -> list:
        """自动翻页获取所有数据"""
        all_data = []
        page_no = 0

        while True:
            result = method_func(page_no=page_no, page_size=page_size, **kwargs)
            data_list = result.get('data', {}).get('data_list', [])

            if not data_list:
                break

            all_data.extend(data_list)

            total_count = result.get('data', {}).get('total_count', 0)
            if len(all_data) >= total_count:
                break

            page_no += 1

        return all_data


# 全局客户端实例
wdt_client = WDTClient()
