# Copyright (c) 2022 Advanced Micro Devices, Inc.  All Rights Reserved

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import contextlib
import os
import re
import sys

class AMDPythonTracer:

    @staticmethod
    def main() -> None:
        trace_opts = sys.argv[1]
        output_file = sys.argv[2]
        sys.argv = sys.argv[3:] 

        script_path = os.path.dirname(os.path.abspath(__file__)) + "/ProfileAgents/x64/"

        sys.path.insert(1, script_path)
        import libAMDTPythonAgent as agent

        try:
            target_script = None
            try:
                target_script = [x for x in sys.argv if re.match(".*\.py$", x)]
                with open(target_script[0], "rb") as profile_prog:
                    try:
                        code = compile(
                            profile_prog.read(),
                            target_script[0],
                            "exec",
                        )
                    except SyntaxError:
                        traceback.print_exc()
                        sys.exit(1)
                    program_path = os.path.dirname(os.path.abspath(target_script[0]))
                    sys.path.insert(0, program_path)
                    
                    import __main__

                    locals = __main__.__dict__
                    globals = __main__.__dict__
                    globals["__file__"] = os.path.abspath(target_script[0])
                    globals["__spec__"] = None

                    agent.AMDTOpenRawTraceFile(output_file)
                    if (trace_opts == "FUNCTION_ONLY"):
                        agent.AMDTEnFunctionProfile()
                    elif (trace_opts == "FUNCTION_TARGET_SRC"):
                        agent.AMDTEnTargetSrcProfile()
                    elif (trace_opts == "ALL"):
                        agent.AMDTEnAlllSourceProfile()

                    exec(code, globals, locals)
                    agent.AMDTCloseRawTraceFile()

            except (FileNotFoundError, IOError):
                if target_script:
                    print("AMDPythonTracer: could not find input file " + target_script[0])
                else:
                    print("AMDPythonTracer: no input file specified.")
                sys.exit(1)
        except SystemExit:
            pass
        except Exception:
            print("AMDPythonTracer failed to initialize.\n" + traceback.format_exc())
            sys.exit(1)
        finally:
            sys.exit(0)


if __name__ == "__main__":
    AMDPythonTracer.main()
