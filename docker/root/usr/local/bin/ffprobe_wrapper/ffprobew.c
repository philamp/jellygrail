#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <stdint.h>
#include <arpa/inet.h>

#define SOCKET_PATH "/tmp/jelly_ffprobe_socket"
#define BUFFER_SIZE 1024

int read_all(int fd, void *buf, size_t count) {
    size_t bytes_read = 0;
    ssize_t result;
    while (bytes_read < count) {
        result = read(fd, (char *)buf + bytes_read, count - bytes_read);
        if (result < 0) {
            return -1;
        }
        bytes_read += result;
    }
    return 0;
}

int main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <file_path>\n", argv[0]);
        exit(EXIT_FAILURE);
    }

    const char *file_path = argv[1];
    int sockfd;
    struct sockaddr_un serv_addr;
    char buffer[BUFFER_SIZE];

    // Create socket
    sockfd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sockfd < 0) {
        printf("Error opening socket");
    }

    memset(&serv_addr, 0, sizeof(serv_addr));
    serv_addr.sun_family = AF_UNIX;
    strncpy(serv_addr.sun_path, SOCKET_PATH, sizeof(serv_addr.sun_path) - 1);

    // Connect to the server
    if (connect(sockfd, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) < 0) {
        printf("Error connecting");
    }

    // Send the file path to the server
    if (write(sockfd, file_path, strlen(file_path)) < 0) {
        printf("Error writing to socket");
    }

    // Read the length of stdout
    uint32_t stdout_length;
    if (read_all(sockfd, &stdout_length, sizeof(stdout_length)) < 0) {
        printf("Error reading stdout length");
    }
    stdout_length = ntohl(stdout_length); // Convert from network byte order

    // Read stdout data
    char *stdout_data = malloc(stdout_length + 1);
    if (stdout_data == NULL) {
        printf("Error allocating memory for stdout data");
    }
    if (read_all(sockfd, stdout_data, stdout_length) < 0) {
        printf("Error reading stdout data");
    }
    stdout_data[stdout_length] = '\0'; // Null-terminate the string

    // Read the length of stderr
    uint32_t stderr_length;
    if (read_all(sockfd, &stderr_length, sizeof(stderr_length)) < 0) {
        printf("Error reading stderr length");
    }
    stderr_length = ntohl(stderr_length); // Convert from network byte order

    // Read stderr data
    char *stderr_data = malloc(stderr_length + 1);
    if (stderr_data == NULL) {
        printf("Error allocating memory for stderr data");
    }
    if (read_all(sockfd, stderr_data, stderr_length) < 0) {
        printf("Error reading stderr data");
    }
    stderr_data[stderr_length] = '\0'; // Null-terminate the string

    // Read the return code
    int32_t return_code;
    if (read_all(sockfd, &return_code, sizeof(return_code)) < 0) {
        printf("Error reading return code");
    }
    return_code = ntohl(return_code); // Convert from network byte order

    // Close the socket
    close(sockfd);

    // Print stdout and stderr
    printf("stdout: %s\n", stdout_data);
    printf("error code: %d\n", return_code);
    fprintf(stderr, "stderr: %s\n", stderr_data);

    // Clean up
    free(stdout_data);
    free(stderr_data);



    // Exit with the return code from the server
    return return_code;
}