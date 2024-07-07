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

    if (argc < 3) {
        fprintf(stderr, "Usage: %s <arg1> <arg2> [... <argN>]\n", argv[0]);
        exit(EXIT_FAILURE);
    }

    // Combine all arguments into a single string
    size_t total_length = 0;
    for (int i = 1; i < argc; ++i) {
        total_length += strlen(argv[i]) + 3; // +1 for space or null terminator
    }

    char *combined_args = malloc(total_length);
    if (combined_args == NULL) {
        fprintf(stderr, "Error allocating memory for combined arguments\n");
        exit(EXIT_FAILURE);
    }

    combined_args[0] = '"';
    for (int i = 1; i < argc; ++i) {
        strcat(combined_args, argv[i]);
        if (i < argc - 1) {
            strcat(combined_args, "\" \"");
        }
    }
    strcat(combined_args, "\"");

    int sockfd;
    struct sockaddr_un serv_addr;
    char buffer[BUFFER_SIZE];

    // Create socket
    sockfd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sockfd < 0) {
        fprintf(stderr, "Error opening socket\n");
    }

    memset(&serv_addr, 0, sizeof(serv_addr));
    serv_addr.sun_family = AF_UNIX;
    strncpy(serv_addr.sun_path, SOCKET_PATH, sizeof(serv_addr.sun_path) - 1);

    // Connect to the server
    if (connect(sockfd, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) < 0) {
        fprintf(stderr, "Error connecting\n");
        close(sockfd);
        free(combined_args);
        return(EXIT_FAILURE);
    }

    // Send the file path to the server
    if (write(sockfd, combined_args, strlen(combined_args)) < 0) {
        fprintf(stderr, "Error writing to socket\n");
        close(sockfd);
        free(combined_args);
        return(EXIT_FAILURE);
    }

    free(combined_args);

    // Read the length of stdout
    uint32_t stdout_length;
    if (read_all(sockfd, &stdout_length, sizeof(stdout_length)) < 0) {
        fprintf(stderr, "Error reading stdout length\n");
        close(sockfd);
        return(EXIT_FAILURE);        
    }
    stdout_length = ntohl(stdout_length); // Convert from network byte order

    // Read stdout data
    char *stdout_data = malloc(stdout_length + 1);
    if (stdout_data == NULL) {
        fprintf(stderr, "Error allocating memory for stdout data\n");
        close(sockfd);
        return(EXIT_FAILURE);
    }
    if (read_all(sockfd, stdout_data, stdout_length) < 0) {
        fprintf(stderr, "Error reading stdout data\n");
        close(sockfd);
        free(stdout_data);
        return(EXIT_FAILURE);
    }
    stdout_data[stdout_length] = '\0'; // Null-terminate the string

    // Read the length of stderr
    uint32_t stderr_length;
    if (read_all(sockfd, &stderr_length, sizeof(stderr_length)) < 0) {
        fprintf(stderr, "Error reading stderr length\n");
        close(sockfd);
        free(stdout_data);
        return(EXIT_FAILURE);
    }
    stderr_length = ntohl(stderr_length); // Convert from network byte order

    // Read stderr data
    char *stderr_data = malloc(stderr_length + 1);
    if (stderr_data == NULL) {
        fprintf(stderr, "Error allocating memory for stderr data\n");
        close(sockfd);
        free(stdout_data);
        return(EXIT_FAILURE);
    }
    if (read_all(sockfd, stderr_data, stderr_length) < 0) {
        fprintf(stderr, "Error reading stderr data\n");
        close(sockfd);
        free(stderr_data); 
        free(stdout_data);
        return(EXIT_FAILURE);
    }
    stderr_data[stderr_length] = '\0'; // Null-terminate the string

    // Read the return code
    int32_t return_code;
    if (read_all(sockfd, &return_code, sizeof(return_code)) < 0) {
        fprintf(stderr, "Error reading return code\n");
        close(sockfd);
        free(stderr_data); 
        free(stdout_data);
        return(EXIT_FAILURE);
    }
    return_code = ntohl(return_code); // Convert from network byte order

    // Close the socket
    close(sockfd);

    // Print stdout and stderr
    // adjusted temporarily for debug
    printf(stdout_data);
    //printf("-----"); ------------- debug here
    //printf("error code: %d\n", return_code); ------------- debug here
    fprintf(stderr, stderr_data);

    // Clean up
    free(stdout_data);
    free(stderr_data);

    // Exit with the return code from the server
    return return_code;
}