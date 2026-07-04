/*
 * ATK-Logic Proxy DLL — zero-CRT, kernel32/user32/ws2_32 only.
 *
 * All exports → Qt5Network_real.dll (via .def forwarding).
 * DllMain spins up a TCP server on 127.0.0.1:9876.
 *
 * Build: see build.ps1
 */
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif

#include <windows.h>
#include <winsock2.h>

/* ── Constants ──────────────────────────────────────────────────────────── */
#define TCP_PORT     9876
#define GUI_CLASS    L"Qt5152QWindowOwnDCIcon"
#define GUI_TITLE    L"ATK-LogicView - DL16"
#define BUF_SIZE     4096
#define WATCH_DIR    L"D:\\Programs\\ATK-Logic\\test\\"

/* ── Helpers (no CRT) ───────────────────────────────────────────────────── */
static int my_strcmp(const char *a, const char *b)
{
    while (*a && *b && *a == *b) { a++; b++; }
    return (unsigned char)*a - (unsigned char)*b;
}

static int my_strncmp(const char *a, const char *b, int n)
{
    int i;
    for (i = 0; i < n; i++) { if (a[i] != b[i]) return (unsigned char)a[i] - (unsigned char)b[i]; if (!a[i]) return 0; }
    return 0;
}

static int my_strlen(const char *s)
{
    const char *p = s;
    while (*p) p++;
    return (int)(p - s);
}

static const char *my_strstr(const char *haystack, const char *needle)
{
    int nlen = my_strlen(needle);
    if (nlen == 0) return haystack;
    while (*haystack) {
        if (*haystack == *needle && my_strncmp(haystack, needle, nlen) == 0)
            return haystack;
        haystack++;
    }
    return NULL;
}

static double my_strtod(const char *s)
{
    double result = 0.0, sign = 1.0, frac = 0.0, div = 1.0;
    int has_frac = 0;
    while (*s == ' ' || *s == '\t') s++;
    if (*s == '-') { sign = -1.0; s++; }
    else if (*s == '+') s++;
    while (*s >= '0' && *s <= '9') { result = result * 10.0 + (*s - '0'); s++; }
    if (*s == '.') {
        s++;
        while (*s >= '0' && *s <= '9') { frac = frac * 10.0 + (*s - '0'); div *= 10.0; s++; has_frac = 1; }
    }
    result += frac / div;
    return result * sign;
    (void)has_frac;
}

/* Minimal itoa */
static void my_itoa(int val, char *out)
{
    char tmp[16];
    int i = 0, neg = 0;
    if (val < 0) { neg = 1; val = -val; }
    if (val == 0) { out[0] = '0'; out[1] = '\0'; return; }
    while (val > 0) { tmp[i++] = '0' + (val % 10); val /= 10; }
    if (neg) tmp[i++] = '-';
    int j = 0;
    while (i > 0) out[j++] = tmp[--i];
    out[j] = '\0';
}

static void my_strcpy(char *dst, const char *src)
{
    while (*src) *dst++ = *src++;
    *dst = '\0';
}

/* Simple JSON string extract: find "key":"value" and return value */
static int json_get_strval(const char *json, const char *key, char *out, int out_max)
{
    int klen = my_strlen(key);
    /* Search for "key" */
    char search[128];
    int i;
    search[0] = '"';
    for (i = 0; i < klen && i < 120; i++) search[i + 1] = key[i];
    search[i + 1] = '"';
    search[i + 2] = '\0';

    const char *p = my_strstr(json, search);
    if (!p) return 0;
    p += klen + 2; /* skip "key" */

    while (*p == ' ' || *p == ':' || *p == '\t') p++;
    if (*p != '"') return 0;
    p++;
    int j = 0;
    while (*p && *p != '"' && j < out_max - 1) { out[j++] = *p++; }
    out[j] = '\0';
    return 1;
}

/* Find numeric value for key */
static double json_get_numval(const char *json, const char *key, double def)
{
    int klen = my_strlen(key);
    char search[128];
    int i;
    search[0] = '"';
    for (i = 0; i < klen && i < 120; i++) search[i + 1] = key[i];
    search[i + 1] = '"';
    search[i + 2] = '\0';

    const char *p = my_strstr(json, search);
    if (!p) return def;
    p += klen + 2;
    while (*p == ' ' || *p == ':' || *p == '\t') p++;
    return my_strtod(p);
}

/* Build a JSON response string */
static int build_response(char *buf, int buf_size, const char *status,
                          const char *k1, const char *v1,
                          const char *k2, const char *v2)
{
    int pos = 0;
    /* write: {"status":" */
    buf[pos++] = '{'; buf[pos++] = '"'; buf[pos++] = 's'; buf[pos++] = 't';
    buf[pos++] = 'a'; buf[pos++] = 't'; buf[pos++] = 'u'; buf[pos++] = 's';
    buf[pos++] = '"'; buf[pos++] = ':'; buf[pos++] = '"';
    {
        const char *s = status;
        while (*s && pos < buf_size - 1) buf[pos++] = *s++;
    }
    buf[pos++] = '"';

    if (k1 && v1 && pos < buf_size - 10) {
        buf[pos++] = ',';
        buf[pos++] = '"';
        { const char *s = k1; while (*s && pos < buf_size - 1) buf[pos++] = *s++; }
        buf[pos++] = '"'; buf[pos++] = ':'; buf[pos++] = '"';
        { const char *s = v1; while (*s && pos < buf_size - 1) buf[pos++] = *s++; }
        buf[pos++] = '"';
    }
    if (k2 && v2 && pos < buf_size - 10) {
        buf[pos++] = ',';
        buf[pos++] = '"';
        { const char *s = k2; while (*s && pos < buf_size - 1) buf[pos++] = *s++; }
        buf[pos++] = '"'; buf[pos++] = ':'; buf[pos++] = '"';
        { const char *s = v2; while (*s && pos < buf_size - 1) buf[pos++] = *s++; }
        buf[pos++] = '"';
    }
    buf[pos++] = '}'; buf[pos++] = '\n'; buf[pos] = '\0';
    return pos;
}

/* ── Globals ────────────────────────────────────────────────────────────── */
static SOCKET    g_listen  = INVALID_SOCKET;
static SOCKET    g_client  = 0;  /* 0 = no client, compared against NULL */
static volatile LONG g_running   = 1;
static volatile LONG g_capturing = 0;
static volatile LONG g_is_ctrl_s_pressed = 0;
static volatile LONG g_preflight_ok     = 0;
static HANDLE    g_thread  = NULL;

/* Forward declaration */
static void dbg_log(const char *msg);

/* ── GUI helpers ────────────────────────────────────────────────────────── */
static HWND find_window(void)
{
    /* Try by class+title, then title-only (class may vary) */
    HWND h = FindWindowW(GUI_CLASS, GUI_TITLE);
    if (!h) {
        h = FindWindowW(NULL, GUI_TITLE);
    }
    return h;
}

static int focus_window(void)
{
    HWND h = find_window();
    if (!h) {
        dbg_log("focus_window: FindWindowW FAILED");
        return 0;
    }
    dbg_log("focus_window: window found, focusing...");

    /* AttachThreadInput: attach our thread to the foreground thread's
     * input queue, which gives us SetForegroundWindow permission. */
    HWND fg = GetForegroundWindow();
    if (fg) {
        DWORD my_tid = GetCurrentThreadId();
        DWORD fg_tid = GetWindowThreadProcessId(fg, NULL);
        if (my_tid != fg_tid) {
            AttachThreadInput(my_tid, fg_tid, TRUE);
            SetForegroundWindow(h);
            BringWindowToTop(h);
            Sleep(150);
            AttachThreadInput(my_tid, fg_tid, FALSE);
            return 1;
        }
    }

    /* Fallback: try direct */
    AllowSetForegroundWindow(ASFW_ANY);
    SetForegroundWindow(h);
    BringWindowToTop(h);
    Sleep(150);
    return 1;
}

/* Retry focus_window() until it succeeds or timeout expires.
   Returns 1 if window was found, 0 if timeout. */
static int focus_window_retry(int timeout_ms)
{
    int waited = 0;
    while (waited < timeout_ms) {
        if (focus_window()) return 1;
        Sleep(400);
        waited += 400;
    }
    dbg_log("focus_window_retry: TIMEOUT - window never appeared");
    return 0;
}

/* Send a single key via system-level keybd_event (needs window focus) */
static void press_vkey(BYTE vk)
{
    keybd_event(vk, 0, 0, 0);
    Sleep(30);
    keybd_event(vk, 0, KEYEVENTF_KEYUP, 0);
}

/* Send modifier + key combo via system-level keybd_event */
static void send_mod_combo(BYTE mod1, BYTE mod2, BYTE key)
{
    keybd_event(mod1, 0, 0, 0);
    Sleep(20);
    if (mod2) { keybd_event(mod2, 0, 0, 0); Sleep(20); }
    keybd_event(key, 0, 0, 0);
    Sleep(30);
    keybd_event(key, 0, KEYEVENTF_KEYUP, 0);
    Sleep(20);
    if (mod2) { keybd_event(mod2, 0, KEYEVENTF_KEYUP, 0); Sleep(20); }
    keybd_event(mod1, 0, KEYEVENTF_KEYUP, 0);
}

/* Set clipboard text and paste it */
static int paste_text(const char *text)
{
    int len = 0;
    { const char *p = text; while (*p) len++, p++; }

    if (!OpenClipboard(NULL)) return 0;
    EmptyClipboard();

    HGLOBAL hMem = GlobalAlloc(GMEM_MOVEABLE, len + 1);
    if (hMem) {
        char *dst = (char *)GlobalLock(hMem);
        if (dst) {
            { int i; for (i = 0; i <= len; i++) dst[i] = text[i]; }
            GlobalUnlock(hMem);
        }
        SetClipboardData(CF_TEXT, hMem);
    }
    CloseClipboard();

    /* Paste: Ctrl+V */
    Sleep(100);
    keybd_event(VK_CONTROL, 0, 0, 0);
    Sleep(20);
    press_vkey('V');
    keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0);
    return 1;
}

/* Type Enter key */
static void press_enter(void)
{
    press_vkey(VK_RETURN);
}

/* ── File watch ─────────────────────────────────────────────────────────── */
/* Find newest .atkdl newer than baseline; returns 1 and writes name */
static int find_new_file(char *out, int out_max, const FILETIME *baseline)
{
    WIN32_FIND_DATAW fd;
    HANDLE h;
    WCHAR pattern[320];
    FILETIME best = {0};
    WCHAR best_name[260] = {0};

    /* build WATCH_DIR*.atkdl */
    {
        const WCHAR *src = WATCH_DIR;
        int i = 0;
        while (*src && i < 310) pattern[i++] = *src++;
        pattern[i++] = '*'; pattern[i++] = '.'; pattern[i++] = 'a';
        pattern[i++] = 't'; pattern[i++] = 'k'; pattern[i++] = 'd';
        pattern[i++] = 'l'; pattern[i] = 0;
    }

    h = FindFirstFileW(pattern, &fd);
    if (h == INVALID_HANDLE_VALUE) return 0;

    do {
        if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) {
            if (CompareFileTime(&fd.ftCreationTime, baseline) > 0 &&
                CompareFileTime(&fd.ftCreationTime, &best) > 0) {
                best = fd.ftCreationTime;
                /* copy fd.cFileName to best_name */
                { int j = 0; while (fd.cFileName[j] && j < 259) { best_name[j] = fd.cFileName[j]; j++; } best_name[j] = 0; }
            }
        }
    } while (FindNextFileW(h, &fd));
    FindClose(h);

    if (best_name[0] == 0) return 0;

    /* Convert to UTF-8 */
    WideCharToMultiByte(CP_UTF8, 0, best_name, -1, out, out_max, NULL, NULL);
    return 1;
}

/* Copy file using Win32 */
static int copy_file_w(const WCHAR *src, const WCHAR *dst)
{
    /* Ensure parent dirs exist */
    WCHAR tmp[520];
    { int j = 0; while (dst[j] && j < 510) { tmp[j] = dst[j]; j++; } tmp[j] = 0; }
    WCHAR *p = tmp;
    while (*p) {
        if (*p == L'\\' || *p == L'/') {
            WCHAR saved = *p;
            *p = 0;
            CreateDirectoryW(tmp, NULL);
            *p = saved;
        }
        p++;
    }
    CreateDirectoryW(tmp, NULL);
    return CopyFileW(src, dst, FALSE) ? 1 : 0;
}

/* Use static buffers to avoid large stack frames */
static char g_buf[BUF_SIZE];
static char g_resp[BUF_SIZE];
static char g_cmd[32];
static char g_output[512];
static char g_new_file[512];
static char g_sched[16];
static WCHAR g_w_src[520];
static WCHAR g_w_dst[520];

/* Debug log to file */
static void dbg_log(const char *msg)
{
    HANDLE f = CreateFileA("D:\\proxy_debug.log",
        FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f != INVALID_HANDLE_VALUE) {
        DWORD w;
        /* Timestamp */
        SYSTEMTIME st;
        GetLocalTime(&st);
        char ts[64];
        {
            ts[0] = '0' + (st.wHour / 10); ts[1] = '0' + (st.wHour % 10); ts[2] = ':';
            ts[3] = '0' + (st.wMinute / 10); ts[4] = '0' + (st.wMinute % 10); ts[5] = ':';
            ts[6] = '0' + (st.wSecond / 10); ts[7] = '0' + (st.wSecond % 10); ts[8] = ' ';
            ts[9] = 0;
        }
        WriteFile(f, ts, 9, &w, NULL);
        {
            int l = 0; while (msg[l]) l++;
            WriteFile(f, msg, l, &w, NULL);
        }
        WriteFile(f, "\r\n", 2, &w, NULL);
        CloseHandle(f);
    }
}

static void dbg_enum_windows(void)
{
    WCHAR title[256];
    char buf[512];
    HWND w = GetTopWindow(NULL);
    while (w) {
        if (GetWindowTextW(w, title, 255) > 0) {
            int j = 0;
            buf[j++] = ' '; buf[j++] = '"';
            {
                int k = 0;
                while (title[k] && j < 500) {
                    if (title[k] < 128) buf[j++] = (char)title[k];
                    else { buf[j++] = '?'; }
                    k++;
                }
            }
            buf[j++] = '"'; buf[j] = 0;
            dbg_log(buf);
        }
        w = GetWindow(w, GW_HWNDNEXT);
    }
}

/* ── Client handler ─────────────────────────────────────────────────────── */
static void handle_client(SOCKET s)
{
    char *buf  = g_buf;
    char *resp = g_resp;
    int n;
    const char *hardcoded = "{\"status\":\"ok\"}\n";
    int hlen = 0;
    {
        const char *p = hardcoded;
        while (*p) hlen++, p++;
    }

    n = recv(s, buf, BUF_SIZE - 1, 0);
    if (n <= 0) return;
    buf[n] = '\0';

    /* Get "cmd" value */
    char *cmd = g_cmd;
    { int ii; for (ii = 0; ii < 32; ii++) cmd[ii] = 0; }
    json_get_strval(buf, "cmd", cmd, 31);

    if (my_strcmp(cmd, "start") == 0) {
        if (InterlockedCompareExchange(&g_capturing, 1, 0) != 0) {
            int len = build_response(resp, BUF_SIZE, "error", "msg", "capture already running", NULL, NULL);
            send(s, resp, len, 0);
            return;
        }

        double dur_s = json_get_numval(buf, "duration_s", 2.0);
        char *output = g_output;
        { int ii; for (ii = 0; ii < 512; ii++) output[ii] = 0; }
        json_get_strval(buf, "output", output, 511);

        /* Send initial progress */
        {
            int len = build_response(resp, BUF_SIZE, "progress", "phase", "capture", "schedule", "0");
            send(s, resp, len, 0);
        }

        /* Step 1: F1 = start capture (retry window focus — Qt may still
           be creating the window when the TCP server starts in DllMain) */
        dbg_log("start: sending F1...");
        if (!focus_window_retry(10000)) {
            dbg_log("start: ERROR - window never appeared, cannot start capture");
            int len = build_response(resp, BUF_SIZE, "error",
                "msg", "GUI window not found after 10s — retry", NULL, NULL);
            send(s, resp, len, 0);
            InterlockedExchange(&g_capturing, 0);
            return;
        }
        press_vkey(VK_F1);
        dbg_log("start: F1 sent, capturing...");

        /* Step 2: wait for requested duration */
        int cap_ms = (int)(dur_s * 1000);
        int waited = 0;
        while (waited < cap_ms && g_running) {
            Sleep(500);
            waited += 500;
            if (waited % 2000 == 0) {
                int pct = (int)((double)waited / (double)cap_ms * 50.0);
                if (pct > 49) pct = 49;
                char *sched = g_sched;
                my_itoa(pct, sched);
                int len = build_response(resp, BUF_SIZE, "progress", "phase", "capture", "schedule", sched);
                send(s, resp, len, 0);
            }
        }

        /* Step 3: F2 = stop capture */
        dbg_log("start: sending F2 to stop...");
        focus_window_retry(3000);
        press_vkey(VK_F2);
        dbg_log("start: F2 sent, waiting for GUI to settle...");
        Sleep(3000); /* wait for GUI to process stop + render */

        /* Step 4: Ctrl+S to save (first time = Save As dialog, subsequent = direct overwrite) */
        dbg_log("start: sending Ctrl+S...");
        focus_window_retry(3000);
        Sleep(300);
        send_mod_combo(VK_CONTROL, 0, 'S');
        dbg_log("start: Ctrl+S sent, detecting picker...");
        Sleep(800);

        /* Detect if Save As picker appeared */
        {
            HWND dlg = FindWindowW(L"#32770", NULL);
            int picker_open = 0;
            /* Walk all top-level #32770 windows */
            while (dlg) {
                WCHAR cls[32];
                if (GetClassNameW(dlg, cls, 31) > 0 && wcscmp(cls, L"#32770") == 0) {
                    WCHAR dlg_title[256];
                    GetWindowTextW(dlg, dlg_title, 255);
                    /* Skip confirm/overwrite dialogs (确认/替换) */
                    if (wcsstr(dlg_title, L"\u786e\u8ba4") == NULL &&
                        wcsstr(dlg_title, L"\u66ff\u6362") == NULL) {
                        picker_open = 1;
                        break;
                    }
                }
                dlg = GetWindow(dlg, GW_HWNDNEXT);
            }

            if (picker_open) {
                dbg_log("start: save picker detected");
                if (output[0]) {
                    int len = build_response(resp, BUF_SIZE, "ok",
                        "save_prompt", "open", "filename", output);
                    send(s, resp, len, 0);
                } else {
                    int len = build_response(resp, BUF_SIZE, "ok",
                        "save_prompt", "open", NULL, NULL);
                    send(s, resp, len, 0);
                }
            } else {
                dbg_log("start: no save picker — file saved directly");
                if (output[0]) {
                    int len = build_response(resp, BUF_SIZE, "ok",
                        "save_prompt", "none", "filename", output);
                    send(s, resp, len, 0);
                } else {
                    int len = build_response(resp, BUF_SIZE, "ok",
                        "save_prompt", "none", NULL, NULL);
                    send(s, resp, len, 0);
                }
            }
        }
        InterlockedExchange(&g_capturing, 0);
        return;
    } else if (my_strcmp(cmd, "stop") == 0) {
        focus_window();
        press_vkey(VK_F2);
        InterlockedExchange(&g_capturing, 0);
        int len = build_response(resp, BUF_SIZE, "ok", NULL, NULL, NULL, NULL);
        send(s, resp, len, 0);

    } else if (my_strcmp(cmd, "status") == 0) {
        char st[2] = { '0' + (char)g_capturing, '\0' };
        int len = build_response(resp, BUF_SIZE, "ok", "capturing", st, NULL, NULL);
        send(s, resp, len, 0);

    } else if (my_strcmp(cmd, "get_isCtrlSPressed") == 0) {
        char val[2] = { '0' + (char)g_is_ctrl_s_pressed, '\0' };
        int len = build_response(resp, BUF_SIZE, "ok", "value", val, NULL, NULL);
        send(s, resp, len, 0);

    } else if (my_strcmp(cmd, "set_isCtrlSPressed") == 0) {
        double v = json_get_numval(buf, "value", -1.0);
        if (v == 1.0) {
            InterlockedExchange(&g_is_ctrl_s_pressed, 1);
            int len = build_response(resp, BUF_SIZE, "ok", NULL, NULL, NULL, NULL);
            send(s, resp, len, 0);
        } else if (v == 0.0) {
            InterlockedExchange(&g_is_ctrl_s_pressed, 0);
            int len = build_response(resp, BUF_SIZE, "ok", NULL, NULL, NULL, NULL);
            send(s, resp, len, 0);
        } else {
            int len = build_response(resp, BUF_SIZE, "error", "msg", "missing or invalid value", NULL, NULL);
            send(s, resp, len, 0);
        }

    } else if (my_strcmp(cmd, "get_preflight_status") == 0) {
        char val[2] = { '0' + (char)g_preflight_ok, '\0' };
        int len = build_response(resp, BUF_SIZE, "ok", "value", val, NULL, NULL);
        send(s, resp, len, 0);

    } else if (my_strcmp(cmd, "set_preflight_status") == 0) {
        double v = json_get_numval(buf, "value", -1.0);
        if (v == 1.0) {
            InterlockedExchange(&g_preflight_ok, 1);
            int len = build_response(resp, BUF_SIZE, "ok", NULL, NULL, NULL, NULL);
            send(s, resp, len, 0);
        } else if (v == 0.0) {
            InterlockedExchange(&g_preflight_ok, 0);
            int len = build_response(resp, BUF_SIZE, "ok", NULL, NULL, NULL, NULL);
            send(s, resp, len, 0);
        } else {
            int len = build_response(resp, BUF_SIZE, "error", "msg", "missing or invalid value", NULL, NULL);
            send(s, resp, len, 0);
        }

    } else if (my_strcmp(cmd, "file") == 0) {
        /* Find latest existing .atkdl */
        FILETIME zero = {0, 0};
        char latest[512] = "";
        if (find_new_file(latest, sizeof(latest), &zero)) {
            int len = build_response(resp, BUF_SIZE, "ok", "file", latest, NULL, NULL);
            send(s, resp, len, 0);
        } else {
            int len = build_response(resp, BUF_SIZE, "error", "msg", "no .atkdl files", NULL, NULL);
            send(s, resp, len, 0);
        }

    } else {
        int len = build_response(resp, BUF_SIZE, "error", "msg", cmd[0] ? "unknown cmd" : "missing cmd", NULL, NULL);
        send(s, resp, len, 0);
    }
}

/* ── Server thread ──────────────────────────────────────────────────────── */
static DWORD WINAPI server_thread(LPVOID p)
{
    (void)p;
    WSADATA wsa;
    struct sockaddr_in addr;

    if (WSAStartup(MAKEWORD(2, 2), &wsa)) return 1;

    g_listen = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (g_listen == INVALID_SOCKET) { WSACleanup(); return 1; }

    { int opt = 1; setsockopt(g_listen, SOL_SOCKET, SO_REUSEADDR, (const char *)&opt, sizeof(opt)); }

    { int i; for (i = 0; i < (int)sizeof(addr); i++) ((char *)&addr)[i] = 0; }
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = inet_addr("127.0.0.1");
    addr.sin_port = htons(TCP_PORT);

    if (bind(g_listen, (struct sockaddr *)&addr, sizeof(addr))) goto err;
    if (listen(g_listen, 1)) goto err;

    while (g_running) {
        struct timeval tv = {1, 0};
        fd_set fds;
        FD_ZERO(&fds);
        FD_SET(g_listen, &fds);
        if (select(0, &fds, NULL, NULL, &tv) <= 0) continue;

        SOCKET c = accept(g_listen, NULL, NULL);
        if (c == INVALID_SOCKET) continue;

        if (InterlockedCompareExchangePointer((PVOID volatile *)&g_client, (PVOID)(UINT_PTR)c, NULL) != NULL) {
            dbg_log("server: rejecting connection - g_client busy (concurrent connection attempted)");
            closesocket(c);
            continue;
        }

        handle_client(c);
        shutdown(c, SD_SEND);
        Sleep(50);
        closesocket(c);
        InterlockedExchangePointer((PVOID volatile *)&g_client, NULL);
    }

err:
    closesocket(g_listen);
    g_listen = INVALID_SOCKET;
    WSACleanup();
    return 0;
}

/* ── DllMain ────────────────────────────────────────────────────────────── */
BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r)
{
    (void)h; (void)r;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);
        g_is_ctrl_s_pressed = 0;
        g_preflight_ok = 0;
        g_thread = CreateThread(NULL, 0, server_thread, NULL, 0, NULL);
    } else if (reason == DLL_PROCESS_DETACH) {
        g_running = 0;
        if (g_thread) { WaitForSingleObject(g_thread, 3000); CloseHandle(g_thread); }
    }
    return TRUE;
}
