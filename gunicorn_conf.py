import os


bind = '0.0.0.0:%s' % os.environ['PORT']
worker_class = 'aiohttp.worker.GunicornWebWorker'
