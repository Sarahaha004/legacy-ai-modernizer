import subprocess
import os
import platform

class CobolSandbox:
    def __init__(self, cobol_file_path: str):
        self.cobol_file_path = os.path.abspath(cobol_file_path)
        # Windows uses .exe; Unix/Linux uses .bin
        ext = ".exe" if platform.system() == "Windows" else ".bin"
        self.executable_path = os.path.splitext(self.cobol_file_path)[0] + ext

    def get_compiler_flags(self) -> list[str]:
        """
        Inspects the COBOL source file to automatically detect whether
        it uses Free Format (*> comments / unaligned columns) or classic Fixed Format.
        """
        with open(self.cobol_file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # If it has free-format comments (*>) or lacks 6-space margin at line starts
        if "*>" in content or not any(line.startswith(" " * 6) for line in content.splitlines() if line.strip()):
            return ["-x", "-F"]
        return ["-x"]

    def compile(self) -> tuple[bool, str]:
        """Compiles the COBOL file using dynamically detected compiler flags."""
        flags = self.get_compiler_flags()
        cmd = ["cobc"] + flags + ["-o", self.executable_path, self.cobol_file_path]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return False, result.stderr
        return True, "Compilation Successful"

    def execute(self, inputs: list[str]) -> tuple[bool, dict[str, str]]:
        """Executes the compiled binary with sequential stdin inputs."""
        if not os.path.exists(self.executable_path):
            success, msg = self.compile()
            if not success:
                return False, {"error": msg}

        input_data = "\n".join(inputs) + "\n"
        result = subprocess.run(
            [self.executable_path],
            input=input_data,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return False, {"error": result.stderr}

        output_map = {}
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if ":" in line:
                key, val = line.split(":", 1)
                output_map[key.strip()] = val.strip()
        
        return True, output_map

if __name__ == "__main__":
    sandbox = CobolSandbox("tests/synthetic_cobol/loan_risk_engine.cbl")
    compiled, msg = sandbox.compile()
    print("Compilation Status:", msg)
    
    # Deterministic test vector matching the 8 ACCEPT statements
    test_inputs = [
        "CUST9001",
        "750",
        "120000.00",
        "800.00",
        "25000.00",
        "036",
        "F",
        "N"
    ]
    
    ok, output_data = sandbox.execute(test_inputs)
    print("\nDeterministic Legacy Output Map:")
    for k, v in output_data.items():
        print(f"  {k}: {v}")