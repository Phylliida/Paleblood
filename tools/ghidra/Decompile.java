// SPDX-License-Identifier: GPL-2.0-or-later
// Ghidra headless script: decompile functions to C, with a header comment per function.
//
//   analyzeHeadless PROJECT_DIR PROJECT -process eboot.elf -noanalysis \
//       -scriptPath tools/ghidra -postScript Decompile.java OUT.c [LIMIT] [TIMEOUT_MS] [STRIDE]
//
// LIMIT 0 (the default) means every function; TIMEOUT_MS defaults to 120 per function; STRIDE 1
// means every function, and STRIDE n decompiles every nth one, which is how cost is measured
// without paying for the whole catalog: functions are visited in address order and every size
// class is spread across the address range, so a stride samples all of them roughly in
// proportion. Each function prints DECOMPF <address> <size> <ms>, and the last line,
// DECOMP functions=N failed=N ms=N ms_per_function=X, is the run's total. Nothing else in the
// tree says how long the decompiler takes, and reaching the whole catalog depends on that number.
//
// This is raw Ghidra C, not C that compiles: types are undefined8/undefined4, register arguments
// appear as in_RDI, and nothing is renamed. It is the input to a translation pass, not a result.
//@category Export
import java.io.PrintWriter;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;

public class Decompile extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 1) {
            println("DECOMP error: usage: Decompile.java OUT.c [LIMIT] [TIMEOUT_MS]");
            return;
        }
        String out = args[0];
        int limit = args.length > 1 ? Integer.parseInt(args[1]) : 0;
        int timeout = args.length > 2 ? Integer.parseInt(args[2]) : 120;
        int stride = args.length > 3 ? Integer.parseInt(args[3]) : 1;

        DecompInterface ifc = new DecompInterface();
        ifc.toggleCCode(true);
        ifc.toggleSyntaxTree(false);
        if (!ifc.openProgram(currentProgram)) {
            println("DECOMP error: the decompiler would not open the program: " + ifc.getLastMessage());
            return;
        }
        int n = 0;
        int seen = 0;
        int failed = 0;
        long t0 = System.currentTimeMillis();
        try (PrintWriter w = new PrintWriter(out)) {
            for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
                if (limit > 0 && n >= limit) {
                    break;
                }
                if (monitor.isCancelled()) {
                    break;
                }
                if (stride > 1 && seen++ % stride != 0) {
                    continue;
                }
                n++;
                long size = f.getBody() == null ? 0 : f.getBody().getNumAddresses();
                w.printf("// %s size=%d name=%s%n", f.getEntryPoint(), size, f.getName());
                long f0 = System.currentTimeMillis();
                DecompileResults r = ifc.decompileFunction(f, timeout, monitor);
                println(String.format("DECOMPF %s %d %d", f.getEntryPoint(), size,
                    System.currentTimeMillis() - f0));
                if (r != null && r.decompileCompleted()) {
                    w.println(r.getDecompiledFunction().getC());
                } else {
                    failed++;
                    w.printf("// DECOMPILE FAILED: %s%n", r == null ? "no result" : r.getErrorMessage());
                }
                w.println();
            }
        }
        ifc.dispose();
        long ms = System.currentTimeMillis() - t0;
        println(String.format("DECOMP functions=%d failed=%d ms=%d ms_per_function=%.1f", n, failed, ms,
            n == 0 ? 0.0 : (double) ms / n));
    }
}
