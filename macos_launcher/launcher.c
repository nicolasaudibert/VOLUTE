/* Bundle executable: locates Contents/Resources/run.sh next to itself and runs
   it. Resolving its own path keeps the bundle movable (Dock, /Applications).

   install_app_bundle_macos.sh compiles this file when a C compiler is present,
   and otherwise copies the universal binary "launcher" beside it, rebuilt with:
       cc -O2 -arch arm64 -arch x86_64 -mmacosx-version-min=10.15 \
          -o launcher launcher.c */
#include <libgen.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(void) {
    char exec_path[PATH_MAX], resolved[PATH_MAX], script[PATH_MAX];
    uint32_t size = sizeof(exec_path);

    if (_NSGetExecutablePath(exec_path, &size) != 0) return 127;
    if (realpath(exec_path, resolved) == NULL) return 127;

    /* <bundle>/Contents/MacOS/launcher -> <bundle>/Contents */
    char macos_dir[PATH_MAX];
    snprintf(macos_dir, sizeof(macos_dir), "%s", dirname(resolved));
    char contents_dir[PATH_MAX];
    snprintf(contents_dir, sizeof(contents_dir), "%s", dirname(macos_dir));
    snprintf(script, sizeof(script), "%s/Resources/run.sh", contents_dir);

    execl("/bin/bash", "bash", script, contents_dir, (char *)NULL);
    return 127;
}
