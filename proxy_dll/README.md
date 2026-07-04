# ATK-Logic Proxy DLL

## Build

Requires MSVC x64
(`D:\Programs\MSStudio\CommunityApp\VC\Auxiliary\Build\vcvars64.bat`).

```pwsh
.\build.ps1             # Release, default
.\build.ps1 -Build Debug
```

Outputs `Qt5Network.dll` + `.lib` + `.exp` + `proxy_main.obj` into
`outdll/`. The `.def` file is consumed from the source dir.

## Deploy

Target: `D:\Programs\ATK-Logic\` — must already contain the real
Qt5Network runtime renamed to `Qt5Network_real.dll` (the proxy's `.def`
forwards every symbol to it).

```pwsh
Copy-Item outdll\Qt5Network.dll   D:\Programs\ATK-Logic\Qt5Network.dll -Force
```