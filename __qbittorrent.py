# coding=utf-8
# Created By Xushier  QQ:1575659493

'''
变量
export qb_url=""
export username=""
export password=""
export pushplus_token=""
'''

from __logger import Logger
from __notifier import SendNotify
import requests,json,time,sys,os

############### QB参数################
try:
    qb_url   = os.environ['qb_url']
    username = os.environ['username']
    password = os.environ['password']

###############通知参数################
    pushplus_token = os.environ['pushplus_token']
except KeyError:
    print("请检查 qb_url username password pushplus_token 变量是否设置！")
    sys.exit(1)

###############其他参数################
filter_filter  = 'all'
filter_limit   = 5
filter_sort    = 'added_on'
filter_reverse = 'False'
delay          = 1
req_times      = 5

class LoginRequired(Exception):
    def __str__(self):
        return 'Please login first.'

class Client(object):
    """class to interact with qBittorrent WEB API"""
    def __init__(self, url=qb_url, username=username, password=password, log_file_name='run.log', verify=False, timeout=(3.05,20)):
        """
        Initialize the client

        :param url: Base URL of the qBittorrent WEB API
        :param verify: Boolean to specify if SSL verification should be done.
                       Defaults to True. 
        :param timeout: How many seconds to wait for the server to send data
                        before giving up, as a float, or a
                        `(connect timeout, read timeout)` tuple.
                       Defaults to None.
        """
        if not url.endswith('/'):
            url += '/'
        self.url      = url + 'api/v2/'
        self.verify   = verify
        self.timeout  = timeout
        self.username = username
        self.password = password
        self.send_notify = SendNotify(pushplus_token)
        self.log = Logger(file_name=log_file_name, level='info', when='D', backCount=5, interval=1)

        session = requests.session()
        login = session.post(self.url + 'auth/login',
                                  data={'username': self.username,
                                        'password': self.password},
                                  verify=self.verify, timeout=self.timeout)
        if login.text == 'Ok.':
            self._is_authenticated = True
            self.session           = session
        else:
            self._is_authenticated = False

    def _get(self, endpoint, **kwargs):
        """
        Method to perform GET request on the API.

        :param endpoint: Endpoint of the API.
        :param kwargs: Other keyword arguments for requests.

        :return: Response of the GET request.
        """
        return self._request(endpoint, 'get', **kwargs)

    def _post(self, endpoint, data, **kwargs):
        """
        Method to perform POST request on the API.

        :param endpoint: Endpoint of the API.
        :param data: POST DATA for the request.
        :param kwargs: Other keyword arguments for requests.

        :return: Response of the POST request.
        """
        return self._request(endpoint, 'post', data, **kwargs)

    def _request(self, endpoint, method, data=None, **kwargs):
        """
        Method to hanle both GET and POST requests.

        :param endpoint: Endpoint of the API.
        :param method: Method of HTTP request.
        :param data: POST DATA for the request.
        :param kwargs: Other keyword arguments.

        :return: Response for the request.
        """
        final_url = self.url + endpoint

        if not self._is_authenticated:
            raise LoginRequired

        kwargs['verify']  = self.verify
        kwargs['timeout'] = self.timeout
        if method == 'get':
            request = self.session.get(final_url, **kwargs)
        else:
            request = self.session.post(final_url, data, **kwargs)

        request.raise_for_status()
        request.encoding = 'utf_8'

        if len(request.text) == 0:
            data = json.loads('{}')
        else:
            try:
                data = json.loads(request.text)
            except ValueError:
                data = request.text

        return data

    def logout(self):
        """
        Logout the current session.
        """
        response = self._get('auth/logout')
        self._is_authenticated = False
        return response

    def get_torrent_info(self, infohash):
        """
        Get details of the torrent.

        :param infohash: INFO HASH of the torrent.
        """
        return self._get('torrents/properties?hash=' + infohash.lower())

    @property
    def global_transfer_info(self):
        """
        :return: dict{} of the global transfer info of qBittorrent.

        """
        return self._get('transfer/info')

    def sync_main_data(self, rid=0):
        """
        Sync the torrents main data by supplied LAST RESPONSE ID.
        Read more @ https://git.io/fxgB8

        :param rid: Response ID of last request.
        """
        return self._get('sync/maindata', params={'rid': rid})

    def filter_torrents(self, **filters):
        """
        Returns a list of torrents matching the supplied filters.

        :param filter: Current status of the torrents.
        :param category: Fetch all torrents with the supplied label.
        :param sort: Sort torrents by.
        :param reverse: Enable reverse sorting.
        :param limit: Limit the number of torrents returned.
        :param offset: Set offset (if less than 0, offset from end).

        :return: list() of torrent with matching filter.
        For example: qb.torrents(filter='downloading', sort='ratio').
        """
        params = {}
        for name, value in filters.items():
            # make sure that old 'status' argument still works
            name = 'filter' if name == 'status' else name
            params[name] = value

        return self._get('torrents/info', params=params)

    @staticmethod
    def _process_infohash_list(infohash_list):
        """
        Method to convert the infohash_list to qBittorrent API friendly values.

        :param infohash_list: List of infohash.
        """
        if isinstance(infohash_list, list):
            data = {'hashes': '|'.join([h.lower() for h in infohash_list])}
        else:
            data = {'hashes': infohash_list.lower()}
        return data

    def add_torrents_from_link(self, link, uplimit:int, savepath:str, category:str, dllimit=60, paused='false'):
        """
        Download torrent using a link.

        :param link: URL Link or list of.
        :param savepath: Path to download the torrent.
        :param category: Label or Category of the torrent(s).

        :return: Empty JSON data.
        """
        if isinstance(link, list): 
            hashes = {"urls": '\n'.join(link), "upLimit": self.mbytes_to_bytes(uplimit, return_type='str'), "dlLimit": self.mbytes_to_bytes(dllimit, return_type='str'), "savepath": savepath, "category": category, "paused": paused}
        else:
            hashes = {"urls": link, "upLimit": self.mbytes_to_bytes(uplimit, return_type='str'), "dlLimit": self.mbytes_to_bytes(dllimit, return_type='str'), "savepath": savepath, "category": category, "paused": paused}
        return self._post('torrents/add', data=hashes)

    def reannounce(self, infohash_list):
        """
        Recheck all torrents.

        :param infohash_list: Single or list() of infohashes; pass 'all' for all torrents.
        """

        data = self._process_infohash_list(infohash_list)
        return self._post('torrents/reannounce', data=data)

    def delete(self, infohash_list, delete_files=True):
        """
        Delete torrents.

        :param infohash_list: Single or list() of infohashes.
        :param delete_files: Whether to delete files along with torrent.
        """
        data = self._process_infohash_list(infohash_list)
        data['deleteFiles'] = json.dumps(delete_files)
        return self._post('torrents/delete', data=data)

    def mbytes_to_bytes(self, mbytes, return_type='int'):
        """
        Download torrent using a link.

        :param link: URL Link or list of.
        :param savepath: Path to download the torrent.
        :param category: Label or Category of the torrent(s).

        :return: Empty JSON data.
        """
        if isinstance(mbytes, (str,int)):
            mbytes = float(mbytes)

        if return_type == 'int':
            return int(mbytes*1048576)
        else:
            return str(int(mbytes*1048576))
    
    def gbytes_to_bytes(self, gbytes, return_type='int'):
        """
        Download torrent using a link.

        :param link: URL Link or list of.
        :param savepath: Path to download the torrent.
        :param category: Label or Category of the torrent(s).

        :return: Empty JSON data.
        """
        if isinstance(gbytes, (str,int)):
            gbytes = float(gbytes)

        if return_type == 'int':
            return int(gbytes*1073741824)
        else:
            return str(int(gbytes*1073741824))
    
    def bytes_to_mbytes(self, bytes, return_type='float'):
        """
        Download torrent using a link.

        :param link: URL Link or list of.
        :param savepath: Path to download the torrent.
        :param category: Label or Category of the torrent(s).

        :return: Empty JSON data.
        """
        if isinstance(bytes, str):
            bytes = int(bytes)
        
        if return_type == 'float':
            return round(bytes / 1048576, 2)
        else:
            return str(round(bytes / 1048576, 2))

    def bytes_to_gbytes(self, bytes, return_type='float'):
        """
        Download torrent using a link.

        :param link: URL Link or list of.
        :param savepath: Path to download the torrent.
        :param category: Label or Category of the torrent(s).

        :return: Empty JSON data.
        """
        if isinstance(bytes, str):
            bytes = int(bytes)
        
        if return_type == 'float':
            return round(bytes / 1073741824, 2)
        else:
            return str(round(bytes / 1073741824, 2))

    def timestamp_to_date(self, timestamp, return_format='%Y-%m-%d %H:%M:%S') -> str:
        """
        Download torrent using a link.

        :param link: URL Link or list of.
        :param savepath: Path to download the torrent.
        :param category: Label or Category of the torrent(s).

        :return: Empty JSON data.
        """
        if isinstance(timestamp, str) or isinstance(timestamp, float):
            timestamp = int(timestamp)

        return time.strftime(return_format, time.localtime(timestamp))

    def date_to_timestamp(self, date:str, input_format='%Y-%m-%d %H:%M:%S', return_type='int'):
        """
        Download torrent using a link.

        :param link: URL Link or list of.
        :param savepath: Path to download the torrent.
        :param category: Label or Category of the torrent(s).

        :return: Empty JSON data.
        """
        struct_time = time.strptime(date, input_format)

        if return_type == 'str':
            return str(int(time.mktime(struct_time)))
        else:
            return int(time.mktime(struct_time))

    def olddate_to_newdate(self, date:str, input_format='%Y-%m-%d %H:%M:%S', return_format='%Y-%m-%d %H:%M:%S') -> str:
        """
        Download torrent using a link.

        :param link: URL Link or list of.
        :param savepath: Path to download the torrent.
        :param category: Label or Category of the torrent(s).

        :return: Empty JSON data.
        """
        if input_format == return_format:
            return date
        else:
            struct_time = time.strptime(date, input_format)
            return time.strftime(return_format, struct_time)
    
    @property
    def global_transfer_info(self):
        """
        :return: dict{} of the global transfer info of qBittorrent.

        """
        return self._get('transfer/info')

    def get_torrents_amount(self):
        return len(self.filter_torrents(filter='downloading')),len(self.filter_torrents(filter='all'))

    def get_satisfied_torrents(self,limit=filter_limit,filter=filter_filter,sort=filter_sort,reverse=filter_reverse,delay=delay,req_times=req_times) -> list:
        dl_account    = self.get_torrents_amount()[0]
        all_account   = self.get_torrents_amount()[1]
        free_space    = self.bytes_to_gbytes(self.sync_main_data()['server_state']['free_space_on_disk'])
        transfer_info = self.global_transfer_info
        dl_gb_data    = self.bytes_to_gbytes(transfer_info['dl_info_data'])
        up_gb_data    = self.bytes_to_gbytes(transfer_info['up_info_data'])
        dl_gb_speed   = transfer_info['dl_info_speed']
        up_gb_speed   = transfer_info['up_info_speed']
        speed_ratio   = round(dl_gb_speed/up_gb_speed,2)
        time_now      = time.localtime().tm_hour

        if 9 <= time_now <= 23:
            self.log.info("当前时间：{}点，可以删种".format(time_now))
            notify_data  = "当前时间：{}点\n".format(time_now)
        else:
            self.log.info("当前时间：{}点，无需删种".format(time_now))
            sys.exit(0)

        if free_space >= 500 and speed_ratio < 3 and all_account < 30 and dl_account < 10:
            self.log.info("可用空间：{} GB，速度比：{}，种子数量：{}，下载数量：{}，无需删种".format(free_space,speed_ratio,all_account,dl_account))
            sys.exit(0)
        else:
            self.log.info("可用空间：{} GB，速度比：{}，种子数量：{}，下载数量：{}，满足删种条件，可以删种".format(free_space,speed_ratio,all_account,dl_account))
            notify_data = notify_data + "可用空间：{} GB\n速度比率：{}\n种子数量：{}\n下载数量：{}\n满足删种条件，可以删种\n\n".format(free_space,speed_ratio,all_account,dl_account)

        names = locals()
        for i in range(1, req_times+1):
            names['hashes' + str(i)] = set()

            torinfo = self.filter_torrents(filter=filter, limit=limit, sort=sort, reverse=reverse)

            for tr in torinfo:
                added_on, completion_on    = self.timestamp_to_date(tr['added_on']), self.timestamp_to_date(tr['completion_on'])
                name, hashcode, category   = tr['name'], tr['hash'], tr['category']
                ratio, size, state         = round(tr['ratio'],2), self.bytes_to_gbytes(tr['size']), tr['state']
                progress, seed_time        = int(tr['progress']*100), tr['seeding_time'] / 3600
                num_leechs, num_seeds      = tr['num_leechs'], tr['num_seeds']
                dlspeed, upspeed, uploaded = tr['dlspeed'], tr['upspeed'], self.bytes_to_gbytes(tr['uploaded'])

                if state == 'stalledUP' and ( ratio >= 1 or seed_time > 24 ) and num_leechs < 5:
                    self.log.info("删除确认第{}次 - 空闲中 - {} - 已上传：{} GB - 分享率：{} - 完成于：{} - ({})".format(i,category,uploaded,ratio,completion_on,name))
                    names['hashes' + str(i)].add(hashcode)
                if state == 'uploading' and ( ratio >= 1 or seed_time > 24 ) and upspeed < 600*1024 and num_leechs < 5:
                    self.log.info("删除确认第{}次 - 上传中 - {} - 已上传：{} GB - 分享率：{} - 完成于：{} - ({})".format(i,category,uploaded,ratio,completion_on,name))
                    names['hashes' + str(i)].add(hashcode)
                if state == 'downloading' and dlspeed > 20*1048576 and dlspeed / upspeed >= 3 and progress > 15:
                    self.log.info("删除确认第{}次 - 下载中 - {} - 已上传：{} GB - 分享率：{} - 完成于：{} - ({})".format(i,category,uploaded,ratio,completion_on,name))
                    names['hashes' + str(i)].add(hashcode)
                time.sleep(delay)

        final_hashes = names['hashes' + str(1)]
        for n in range(2, req_times+1):
            final_hashes = final_hashes & names['hashes' + str(n)]
        if len(final_hashes):
            for t in list(final_hashes):
                h           = self.get_torrent_info(t)
                t_uploaded, t_ratio = h['total_uploaded'], h['share_ratio']
                t_size      = self.bytes_to_gbytes(h['total_size'])
                t_seedtime  = h['seeding_time'] / 3600
                t_addon     = self.timestamp_to_date(h['addition_date'])
                t_compon    = self.timestamp_to_date(h['completion_date'])
                notify_data = notify_data + "删除 - 添加于：{} - 大小：{} GB - 已上传：{} GB - 分享率：{} - 完成于：{} - 做种时间：{}小时\n".format(t_addon,t_size,t_uploaded,t_ratio,t_compon,t_seedtime)
                time.sleep(delay)
            self.send_notify.pushplus("删种结果", notify_data)
            self.log.info(final_hashes)
            return list(final_hashes)
        else:
            self.log.info("没有符合条件的种子，无需删除")
            self.send_notify.pushplus("删种结果","没有满足删种条件的种子")
            sys.exit(0)