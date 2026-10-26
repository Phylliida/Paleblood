/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Network initialization, modelled as a failure on purpose.

   The boot reached libSceNet sceNetInit (NID Nlev7Lg8k3A, bind 162) at eboot+0xfd1ffa
   (catalogue 0x13d1fff). The caller reads the return code and jumps to a common failure arm on any
   negative value, and that arm skips the rest of the network setup. This runtime has no network state,
   so success would be the claim that needs evidence; a negative return is the guest's own error path,
   and the guest is allowed to take it. The print says which path was taken and why. */
#include "runtime/syslib.h"

#include <stdint.h>
#include <stdio.h>

static unsigned reported;

static int net_init_refused(const void *params)
{
    if (!reported++)
        fprintf(stderr, "pbboot: libSceNet sceNetInit: MODELLED failure (-1), no network state; params=%p "
                        "not dereferenced -- the caller's negative-return arm skips network setup\n", params);
    return -1;
}

RT_SYSLIB_MODELLED("libSceNet", sceNetInit, net_init_refused);

/* libSceHttp sceHttpCreateTemplate (NID 0gYjPTR-6cY, bind 507). The caller stores the return in a
   handle slot and passes it to the next import immediately, so a zero would be a handle the guest uses.
   This runtime has no HTTP state either: return a negative code, which is the guest's own failure arm,
   and say so once. The argument that was 0xffffffff here is the net-init failure code the caller passed
   through; it is printed, not interpreted. */
static unsigned http_reported;

static int http_create_template_refused(int64_t user, const char *url, int type, int flags)
{
    if (!http_reported++)
        fprintf(stderr, "pbboot: libSceHttp sceHttpCreateTemplate: MODELLED failure (-1), no HTTP state; "
                        "user=%lld url=%p type=%d flags=%d -- url not dereferenced\n",
                (long long)user, (const void *)url, type, flags);
    return -1;
}

RT_SYSLIB_MODELLED("libSceHttp", sceHttpCreateTemplate, http_create_template_refused);

/* libSceHttp sceHttpSetNonblock (NID s2-NPIvz+iA, bind 508). The handle here is the -1 the template
   creation returned, so a failure is the consistent answer and the guest's own error arm handles it.
   No HTTP state exists to make nonblocking. */
static unsigned nonblock_reported;

static int http_set_nonblock_refused(int handle, int nonblock)
{
    if (!nonblock_reported++)
        fprintf(stderr, "pbboot: libSceHttp sceHttpSetNonblock: MODELLED failure (-1), no HTTP state; "
                        "handle=%d nonblock=%d\n", handle, nonblock);
    return -1;
}

RT_SYSLIB_MODELLED("libSceHttp", sceHttpSetNonblock, http_set_nonblock_refused);

/* The rest of libSceHttp, refused as a library rather than guessed function by function.

   Every one of these has the same property for this runtime: there is no HTTP state, so any return that
   claims success is a claim with no evidence, while a negative return is the guest's own error path.
   The callers measured so far ignore the return or test it for negative; a caller that tests for zero
   will take its own failure arm, which is the honest outcome. Each name prints once, so the log says
   exactly which calls the guest made instead of one blanket line. Signatures are declared as taking no
   arguments; under the SysV ABI a caller's arguments stay in registers/stack and are ignored, and the
   return is an int64_t in RAX, which is the failure value for every integer- and pointer-returning call
   in this list. */
#define HTTP_REFUSED(sym)                                                                                \
    static unsigned sym##_reported;                                                                      \
    static int64_t sym##_refused(void)                                                                   \
    {                                                                                                    \
        if (!sym##_reported++)                                                                           \
            fprintf(stderr, "pbboot: libSceHttp " #sym ": MODELLED failure (-1), no HTTP state\n");      \
        return -1;                                                                                       \
    }                                                                                                    \
    RT_SYSLIB_MODELLED("libSceHttp", sym, sym##_refused)

HTTP_REFUSED(sceHttpWaitRequest);
HTTP_REFUSED(sceHttpAbortWaitRequest);
HTTP_REFUSED(sceHttpDestroyEpoll);
HTTP_REFUSED(sceHttpDeleteTemplate);
HTTP_REFUSED(sceHttpsEnableOption);
HTTP_REFUSED(sceHttpsDisableOption);
HTTP_REFUSED(sceHttpAddRequestHeader);
HTTP_REFUSED(sceHttpInit);
HTTP_REFUSED(sceHttpTerm);
HTTP_REFUSED(sceHttpCreateConnectionWithURL);
HTTP_REFUSED(sceHttpCreateRequestWithURL);
HTTP_REFUSED(sceHttpSetRequestContentLength);
HTTP_REFUSED(sceHttpSetConnectTimeOut);
HTTP_REFUSED(sceHttpSetEpoll);
HTTP_REFUSED(sceHttpUnsetEpoll);
HTTP_REFUSED(sceHttpDeleteRequest);
HTTP_REFUSED(sceHttpDeleteConnection);
HTTP_REFUSED(sceHttpGetStatusCode);
HTTP_REFUSED(sceHttpGetResponseContentLength);
HTTP_REFUSED(sceHttpReadData);
HTTP_REFUSED(sceHttpSendRequest);
HTTP_REFUSED(sceHttpCreateEpoll);
