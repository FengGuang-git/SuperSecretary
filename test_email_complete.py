import time
import logging
from app.email_gateway import process_once

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('email_complete_test.log'), logging.StreamHandler()]
)

def test_email_receive():
    """完整的邮件接收测试"""
    logging.info('开始完整的邮件接收测试...')
    
    try:
        logging.info('调用process_once()处理邮件...')
        start_time = time.time()
        
        # 运行邮件处理
        process_once(max_retries=3, imap_timeout=60, search_timeout=30)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        logging.info(f'邮件处理完成，耗时: {elapsed_time:.2f}秒')
        print(f'✓ 邮件接收测试成功，耗时: {elapsed_time:.2f}秒')
        return True
        
    except Exception as e:
        logging.error(f'邮件处理出错: {type(e).__name__}: {e}', exc_info=True)
        print(f'✗ 邮件接收测试失败: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_email_receive()
    if success:
        print("\n✓ 邮件接收功能测试通过！")
        print("请检查email_complete_test.log文件查看详细日志")
    else:
        print("\n✗ 邮件接收功能测试失败")
        print("请检查email_complete_test.log文件查看错误详情")