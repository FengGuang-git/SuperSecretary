import time
from app.email_gateway import process_once
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('email_receive_test.log'), logging.StreamHandler()]
)

logging.info('开始邮件接收测试...')

try:
    logging.info('调用process_once()处理邮件...')
    start_time = time.time()
    process_once()
    end_time = time.time()
    logging.info(f'邮件处理完成，耗时: {end_time - start_time:.2f}秒')
    print('邮件接收测试已执行，请查看日志文件email_receive_test.log获取详细信息')
except Exception as e:
    logging.error(f'邮件处理出错: {type(e).__name__}: {e}', exc_info=True)
    print(f'邮件接收测试失败: {e}')
    import traceback
    traceback.print_exc()