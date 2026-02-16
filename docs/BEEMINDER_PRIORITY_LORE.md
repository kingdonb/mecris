# Beeminder Priority Lore: Background Worker Queues

This document summarizes Beeminder's system for managing background tasks, drawing from their internal documentation on worker queues. Understanding these priorities can help in setting and managing Beeminder goals effectively within the Mecris system.

## Worker Queue Overview

Beeminder utilizes a Resque-based system for queuing various jobs, such as sending reminders, regenerating graphs, and processing data. These jobs are categorized into five distinct queues, each with a different priority level:

1.  **`SNAPPY`**:
    *   **Urgency**: Urgent tasks.
    *   **Description**: High-priority jobs that require immediate processing to ensure a responsive user experience.
2.  **`LOCKSY`**:
    *   **Urgency**: Moderately urgent tasks.
    *   **Description**: Tasks that are important but do not require the instantaneous response of `SNAPPY` tasks.
3.  **`BATCHY`**:
    *   **Urgency**: Scheduled batch tasks.
    *   **Description**: Jobs that can be processed in batches on a schedule, such as nightly data aggregations or periodic reports.
4.  **`WHALEY`**:
    *   **Urgency**: Rare, long-running tasks.
    *   **Description**: Tasks that are infrequent but may consume significant resources or take a long time to complete. These are often complex data operations.
5.  **`UNDULY`**:
    *   **Urgency**: Ultra-low priority jobs.
    *   **Description**: Tasks that are non-critical and can be processed when system resources are otherwise idle.

Workers are assigned to these queues to optimize CPU usage and minimize waiting times, ensuring that critical tasks are handled promptly while less urgent tasks are processed efficiently in the background.

## Current Beeminder Goal Status (as of 2026-02-16)

As an important note on goal management, the following Beeminder goals are currently in a **CAUTION** state and will derail in **3 days**:

*   **`ellinika`**: Ελληνικά - Greek language Clozemaster
*   **`reviewstack`**: Cards in Review stack (Clozemaster Arabic)

These goals may require immediate attention to prevent derailing.
