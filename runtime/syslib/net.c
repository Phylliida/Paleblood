/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Network initialization: refuse at the call, because -1 was a fabricated failure.

   The boot reached libSceNet sceNetInit (NID Nlev7Lg8k3A, bind 162) at eboot+0xfd1ffa
   (catalogue 0x13d1fff).  This file used to return -1 on the argument that the caller tests the
   return and takes its own error arm.  It does -- and then, much later, it dereferences the network
   singleton the skipped setup was supposed to publish:

       SIGSEGV at eboot+0x2167870, mov rax,[rdi+0xdc10], rdi == 0

   That is a null global pointer, not a struct field.  Returning -1 did not keep the guest on its
   error path; it left a pointer null and moved the observable failure hundreds of megabytes of guest
   code away from the import that caused it.  A fabricated failure is not more honest than a
   fabricated success: both answer in place of absence, and this one answered a question the guest
   only asked because a real console would have answered 0.

   The honest default is therefore a refusal at the call, before the guest can store a state it does
   not have.  BB_NET_ASSUME_OK=1 is a diagnostic probe: it returns success with no network state and
   exists to find the next named wall, never to be a model.  Measured with it: the 0x2167870 fault
   disappears and the boot reaches libSceNet dgJBaeJnGpo at eboot+0xfd2014 (catalogue 0x13d2014),
   unimplemented.  That is the shape of the missing state; it is not implemented here. */
#include "runtime/process.h"
#include "runtime/syslib.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static unsigned reported;

static int net_init_refused(const void *params)
{
    if (getenv("BB_NET_ASSUME_OK")) {
        if (!reported++)
            fprintf(stderr, "pbboot: libSceNet sceNetInit: PROBE success (0), no network state; params=%p "
                            "not dereferenced -- BB_NET_ASSUME_OK is a diagnostic, not a model\n", params);
        return 0;
    }
    rt_fatal("libSceNet", "sceNetInit: no network state; refusing at the call instead of returning -1, "
                          "which leaves the guest's network singleton null and faults far from here");
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
