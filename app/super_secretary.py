"""
超级秘书服务 - 简化版本
每隔一分钟调用AI Agent检查老板来信和邮件发送需求
"""

import time
import threading
import logging
from typing import Optional
from app.ai_agent import AIAgent

logger = logging.getLogger(__name__)


class SuperSecretary:
    """超级秘书服务类"""
    
    def __init__(self):
        """初始化超级秘书服务"""
        self.ai_agent: Optional[AIAgent] = None
        self.running = False
        self.polling_thread: Optional[threading.Thread] = None
        self.polling_interval = 60  # 每隔60秒轮询一次
        
        logger.info("超级秘书服务初始化完成")
    
    def start(self) -> bool:
        """启动超级秘书服务"""
        try:
            # 如果已经在运行，先停止
            if self.running:
                self.stop()
            
            # 初始化AI Agent
            self.ai_agent = AIAgent()
            
            # 启动轮询线程
            self.running = True
            self.polling_thread = threading.Thread(
                target=self._polling_worker,
                daemon=True,
                name="SuperSecretary-Polling"
            )
            self.polling_thread.start()
            
            logger.info("超级秘书服务启动成功，开始轮询检查")
            return True
            
        except Exception as e:
            logger.error(f"超级秘书服务启动失败: {e}")
            self.running = False
            return False
    
    def stop(self):
        """停止超级秘书服务"""
        self.running = False
        if self.polling_thread and self.polling_thread.is_alive():
            self.polling_thread.join(timeout=5)
        
        logger.info("超级秘书服务已停止")
    
    def _polling_worker(self):
        """轮询工作线程"""
        while self.running:
            try:
                # 调用AI Agent询问老板来信和邮件发送需求
                self._check_boss_messages()
                
                # 等待指定间隔
                for _ in range(self.polling_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"轮询过程中发生错误: {e}")
                # 出错后等待10秒再继续，但确保线程不会退出
                for _ in range(10):
                    if not self.running:
                        break
                    time.sleep(1)
    
    def _check_boss_messages(self):
        """检查老板来信和邮件发送需求"""
        if not self.ai_agent:
            logger.warning("AI Agent未初始化，无法检查消息")
            return
        
        try:
            # 记录本次检查的时间戳
            current_check_time = time.time()
            
            # 构建更明确的询问消息，强调角色定位和邮件上下文识别，使用直接对比方案
            message = f"""
            你是丰光老板的专属秘书多米。请检查老板的邮箱是否有新邮件需要回复。
            
            重要要求：
            1. 首先获取老板收件箱中的所有邮件
            2. 然后获取你的发件箱中已发送的邮件
            3. 对比收件箱和发件箱，识别哪些邮件需要回复
            4. 对于需要回复的邮件，请务必回复
            5. 回复内容要专业、体贴，根据邮件内容进行针对性回复
            6. 如果没有需要回复的邮件，请发送一封问候邮件
            7. 邮件必须使用HTML格式发送
            8. 收件人是老板的邮箱：18696133867@163.com
            9. 发件人是你的邮箱：fengguang2020@foxmail.com
            
            邮件上下文识别规则：
            - 发件人是丰光老板（18696133867@163.com）时，这是老板给你的邮件
            - 收件人是丰光老板（18696133867@163.com）时，这是你给老板的邮件
            - 你的邮箱是多米（fengguang2020@foxmail.com）
            
            邮件去重规则（主题对比方案）：
            - 首先获取老板收件箱中的所有邮件，记录每封邮件的主题
            - 然后获取你的发件箱中已发送的邮件，记录每封邮件的主题
            - 对比主题：如果收件箱中某邮件的主题，在发件箱中已经有相同或高度相似主题的回复，则跳过不再回复
            - 主题匹配标准：完全相同或语义高度相似（如"项目进度"和"项目进展"视为相同主题）
            - 特别注意：必须逐封对比每封邮件的主题内容，确保不重复回复相同主题的邮件
            - 只有当真不存在相同主题的历史回复时，才发送新回复
            
            回复邮件时必须：
            - 开头要明确称呼：'丰总，您好！'或'老板，您好！'
            - 针对邮件内容进行具体回复，不要泛泛而谈
            - 如果老板询问问题，必须给出具体答案
            - 如果老板安排任务，必须确认并说明执行计划
            - 保持专业、礼貌、贴心的语气
            
            注意：通过主题和内容双重对比避免重复回复。回复时要：
            - 首先阅读并理解邮件内容
            - 明确知道这是老板丰光发给你的邮件
            - 以秘书多米的身份进行专业回复
            - 回复内容要针对老板邮件中的具体问题进行回答
            - 不要使用通用回复，必须针对邮件内容
            
            发送邮件前的强制检查步骤（必须严格执行）：
            1. 获取当前要回复邮件的主题和内容大意
            2. 检查发件箱中是否已有相同或相似主题的回复记录
            3. 对比内容大意：分析当前邮件的核心内容、主要问题、关键信息点
            4. 检查发件箱中历史回复的内容大意，判断是否已处理过相同或相似的问题
            5. 主题相似且内容大意重复率超过70%的邮件，必须跳过不再回复
            6. 只有确认主题和内容都确实未回复过，才能发送新回复
            7. 在发送前再次确认：该主题和内容大意在发件箱中无任何相似记录
            
            当前检查时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_check_time))}
            
            请通过对比收件箱和发件箱的方式，识别并回复所有需要处理的邮件，确保每封邮件都得到恰当回复，同时避免重复回复。
            """
      
            # 调用AI Agent处理消息
            response = self.ai_agent.process_message(message)
            
            logger.info(f"AI Agent回复: {response}")
            
            # 记录本次检查结果
            self._log_check_result(current_check_time, response)
            
        except Exception as e:
            logger.error(f"检查老板消息时发生错误: {e}")
    
    def _log_check_result(self, check_time: float, response: str):
        """记录检查结果"""
        # 这里可以添加更详细的日志记录逻辑
        logger.info(f"检查完成于 {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(check_time))}")
        logger.info(f"处理结果: {response[:200]}..." if len(response) > 200 else f"处理结果: {response}")
    
    def is_running(self) -> bool:
        """检查服务是否正在运行"""
        return self.running and self.polling_thread and self.polling_thread.is_alive()
    
    def get_status(self) -> dict:
        """获取服务状态"""
        return {
            "running": self.running,
            "polling_interval": self.polling_interval,
            "ai_agent_ready": self.ai_agent is not None,
            "thread_alive": self.polling_thread and self.polling_thread.is_alive()
        }