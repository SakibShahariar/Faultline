#define _XOPEN_SOURCE 700
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    char executable[PATH_MAX + 1];
    ssize_t length = readlink("/proc/self/exe", executable, PATH_MAX);
    if (length < 0) {
        perror("Faultline: cannot locate AppImage launcher");
        return 1;
    }
    executable[length] = '\0';

    char *separator = strrchr(executable, '/');
    if (separator == NULL) {
        fputs("Faultline: invalid launcher path\n", stderr);
        return 1;
    }
    *separator = '\0';

    char appdir_candidate[PATH_MAX];
    char appdir[PATH_MAX];
    if (snprintf(appdir_candidate, sizeof(appdir_candidate), "%s/../..",
                 executable) >= (int)sizeof(appdir_candidate) ||
        realpath(appdir_candidate, appdir) == NULL) {
        perror("Faultline: cannot resolve AppImage directory");
        return 1;
    }

    char python[PATH_MAX];
    char entrypoint[PATH_MAX];
    if (snprintf(python, sizeof(python), "%s/usr/bin/python3", appdir) >=
            (int)sizeof(python) ||
        snprintf(entrypoint, sizeof(entrypoint),
                 "%s/usr/share/faultline/launch.py", appdir) >=
            (int)sizeof(entrypoint)) {
        fputs("Faultline: AppImage path is too long\n", stderr);
        return 1;
    }

    char **arguments = calloc((size_t)argc + 2, sizeof(char *));
    if (arguments == NULL) {
        perror("Faultline: cannot allocate launcher arguments");
        return 1;
    }
    arguments[0] = python;
    arguments[1] = entrypoint;
    for (int index = 1; index < argc; index++)
        arguments[index + 1] = argv[index];

    execv(python, arguments);
    fprintf(stderr, "Faultline: cannot start bundled Python: %s\n",
            strerror(errno));
    free(arguments);
    return 1;
}
