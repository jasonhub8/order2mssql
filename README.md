# 项目名称：（浏览器自动化）

## ⚠️ 重要声明（必读）
- **本项目仅用于学习研究，严禁非法使用**
- **严禁未经授权抓取酒店后台、客户信息、个人数据**
- **使用前必须获得目标网站/酒店/用户授权**
- **违法使用后果自负，作者不承担任何法律责任**


系统使用说明
1. 浏览器配置
配置 ChromiumOptions，将 Chrome 浏览器中现有的用户数据（userdata）复制到 D:\Default 目录下
用户数据路径查询方式：在 Chrome 地址栏输入 chrome://version/，查看「个人资料路径」获取
首次启动网页时，需手动输入用户名和密码完成初始登录验证
2. 数据库安全配置
修改 MSSQL 数据库连接配置中的密码信息
遵循最小权限原则，建议创建仅具备目标表读取和写入权限的专用数据库用户






-- 创建订单数据表
CREATE TABLE 读取OTA平台订单 (
    -- 自增主键
    id INT IDENTITY(1,1) PRIMARY KEY,
    平台 NVARCHAR(50) NOT NULL,
    -- 订单基本信息
    订单号 NVARCHAR(100) NOT NULL,
    订单状态 NVARCHAR(50),
    入住人 NVARCHAR(200),
    -- 房型信息
    房型名称 NVARCHAR(100),
    
    -- 日期信息
    入住日期 NVARCHAR(100),
    离店日期 NVARCHAR(100),
    天数 NVARCHAR(50),
    间数 NVARCHAR(50),
    
    -- 价格信息
    底价构成s NVARCHAR(500),
    底价构成 DECIMAL(10,2),
    
    -- 早餐信息
    早餐s NVARCHAR(200),
    早餐 NVARCHAR(50),
    
    -- 其他信息
    发票要求 NVARCHAR(200),
    特殊要求 NVARCHAR(500),
    
    -- 创建时间
    创建时间 DATETIME DEFAULT GETDATE()
);

-- 创建索引以提高查询性能
CREATE INDEX idx_订单号 ON 读取OTA平台订单(订单号);
CREATE INDEX idx_平台 ON 读取OTA平台订单(平台);
CREATE INDEX idx_订单状态 ON 读取OTA平台订单(订单状态);
CREATE INDEX idx_入住人 ON 读取OTA平台订单(入住人);

底价构成s：指多天的底价，按顺序。
早餐s：指多天的早餐信息，按顺序。

使用说明：
美团点击详情，或者携程点击订单，程序会自动添加进数据库。（只有点击了才会添加）
如果一下订单状态改变，会自动更新数据库的订单状态。
- 美团： ACCEPTED （已接单）、 CONSUMED （已入住）、 CANCELED （已取消）
- 携程： 已接单 、 已入住 、 已取消 、 已过离店日期

需要放入酒店管理软件根目录运行，自动读取Setting.ini 的服务器配置。

运行后如想退出，右下角小图标。

打包exe #pip install pyinstaller -i https://mirrors.aliyun.com/pypi/simple/
pyinstaller --onefile --noconsole order2mssql.py