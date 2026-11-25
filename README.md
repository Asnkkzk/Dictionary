# 随取词典 WordDict

![词典图标](worddict/assets/worddict.png)

Windows 桌面取词词典，支持翻译、收藏、每日一词及昼夜外观。

## 下载与启动

下载 [WordDict.exe](https://github.com/Asnkkzk/Dictionary/raw/refs/heads/main/dist/WordDict.exe)，双击启动，无需安装 Python。可右键 EXE 创建桌面快捷方式。

- 再次启动会唤起已有主窗口。
- 关闭主窗口后仍驻留托盘；右键词典托盘图标选择「退出」才会结束程序。
- 托盘图标可能位于任务栏的隐藏图标区域。

当前打包版本在 Windows 11 x64、Python 3.13 环境构建。

## 功能与使用

### 取词与本地词典

在其他应用中拖选文本后，可通过浮动菜单翻译或添加单词。翻译依次尝试本地词典、免费在线服务和已配置的官方 API。在线服务需要网络，可用性取决于服务及网络环境。

主窗口支持关键词搜索、A–Z 首字母筛选、查看释义和删除选中词条；历史视图支持重新查询及清空历史。

取词会模拟 Ctrl+C 并读取剪贴板，因此会改变剪贴板内容。部分应用无法通过此方式取词。

### 每日一词

- 从内置的 18 个候选词中排除本地词典已收藏的单词。
- 当日选词保存在配置中；若该词已加入词典，下次查看会选取其他未收藏的词。
- 卡片提供「添加到词典」按钮；候选词全部收藏后会提示暂无新词。
- 「每日一词」菜单可查看今日单词、开关自动提醒及设置提醒小时。
- 再次点击已选提醒时间会取消定时提醒，点击其他时间重新设置。
- 使用电脑本地时间，默认 09:00；到点后约 30 秒内检查，错过时间后启动也会检查。程序需保持运行，每天自动提醒一次。

### 外观

「外观」菜单提供昼间浅色、夜间深色、自定义背景颜色和恢复默认背景。设置自动保存，主窗口与释义卡片同步应用。自定义背景目前为纯色，不包含图片背景。

## 数据与隐私

个人词典、历史和配置保存在 `%APPDATA%\WordDict\`：

- `dict.db`：SQLite 词典与历史
- `config.json`：提醒、外观、可选 API 配置

更新 EXE 不会删除个人数据。备份时请先退出程序，再复制此目录。在线查询会把查询文本发送给所使用的翻译服务；本仓库不包含个人数据库或 API 密钥。

## 从源码运行

建议使用独立 Python 环境（Windows）：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py
```

也可在依赖安装完成后使用 `start.bat`。

## 官方翻译配置（可选）

退出程序后编辑 `%APPDATA%\WordDict\config.json` 中的 `official` 字段，保留其他配置：

```json
{
  "official": {
    "provider": "youdao",
    "youdao_appkey": "YOUR_APP_KEY",
    "youdao_secret": "YOUR_SECRET"
  }
}
```

百度翻译可使用 `provider: "baidu"`，并填写 `baidu_appid`、`baidu_secret`。不要将真实密钥提交到仓库。

## 测试与打包

```powershell
python -m unittest -v test_daily test_system_tray
python -m pip install pyinstaller
python -m PyInstaller --noconfirm WordDict.spec
```

输出为 `dist/WordDict.exe`，包含多尺寸 ICO。覆盖 EXE 前请先退出运行中的程序。测试覆盖每日选词排除与耗尽、跨日提醒、取消提醒时间及后台线程行为；未覆盖所有桌面交互。

## 项目结构

```text
main.py                    启动入口
WordDict.spec              Windows 打包配置
worddict/app.py            主线程与应用调度
worddict/system_tray.py    托盘、鼠标钩子、单实例唤起
worddict/dictionary_window.py  主词典窗口
worddict/popup.py          取词菜单与释义卡片
worddict/daily.py          每日一词
worddict/appearance.py     外观设置
worddict/database.py       本地数据库
worddict/translator.py     翻译服务
worddict/assets/           图标
```
