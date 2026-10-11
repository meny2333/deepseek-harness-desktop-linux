# 个人使用分支

`codex/personal-desktop` 在 GUI 修复与自动构建工具链之上加入实色圆角窗口。

普通窗口使用 12px 圆角；最大化和全屏布局取消圆角。保留顶部悬停显示交通灯、侧栏按钮让位、背景条内保持显示，以及原有的最大化和全屏策略。欢迎页和主界面都强制实色，不向 KWin 请求毛玻璃。

圆角层由 `patches/patch-personal-rounded.py` 应用，包含在全新构建和已有应用树的升级流程中。它仅用于个人分支，不包含在上游 GUI PR 中。

构建 bundled x64 deb：

```sh
./auto-build.sh --arch x64 --formats deb --electron bundled --package-jobs 4
```

默认保留构建缓存；如需在成功后删除解包、打包暂存和应用树，增加 `--clean`。下载缓存仍保留，可在确认成品可用后删除构建存储目录。
