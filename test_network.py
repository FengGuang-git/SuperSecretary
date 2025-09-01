import socket
import time

def test_imap_connection():
    """测试IMAP服务器网络连接"""
    host = "imap.qq.com"
    port = 993
    
    print(f"🔍 测试网络连接到 {host}:{port}")
    
    try:
        # 创建socket连接
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)  # 10秒超时
        
        start_time = time.time()
        sock.connect((host, port))
        end_time = time.time()
        
        print(f"✅ 网络连接成功！耗时: {(end_time - start_time):.2f}秒")
        sock.close()
        return True
        
    except Exception as e:
        print(f"❌ 网络连接失败: {e}")
        return False

def test_dns_resolution():
    """测试DNS解析"""
    host = "imap.qq.com"
    
    print(f"🔍 测试DNS解析 {host}")
    
    try:
        start_time = time.time()
        ip_address = socket.gethostbyname(host)
        end_time = time.time()
        
        print(f"✅ DNS解析成功: {host} -> {ip_address}")
        print(f"📊 解析耗时: {(end_time - start_time):.2f}秒")
        return True
        
    except Exception as e:
        print(f"❌ DNS解析失败: {e}")
        return False

if __name__ == "__main__":
    print("🌐 开始网络连接测试")
    print("=" * 50)
    
    dns_success = test_dns_resolution()
    print()
    
    if dns_success:
        test_imap_connection()
    
    print("\n" + "=" * 50)
    print("📋 网络测试完成")