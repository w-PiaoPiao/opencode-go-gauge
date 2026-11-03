DEGRADED 截图（tablet / light）
【本机无 Tablet 系统镜像】用 2in1 窗口 2000x1500（≈4:3）近似验证平板布局；非真实平板产物，不得作为平板商店图。
================================
本目录的图片不满足页面区分校验：多个 page 的截图完全相同，说明
--ps page <page> 启动参数未生效（旧 HAP 或 AppRoot 未支持初始 tab），
因此不能作为商店素材使用。
验证方式：capture-store-shots.sh 对同一设备+主题下各页截图做 md5 对比，
存在重复即视为参数未生效。
待 Lead 新 HAP（支持 demo/lang/theme/page 调试参数）构建并安装后，重新运行：
  ./capture-store-shots.sh --device tablet --theme light
