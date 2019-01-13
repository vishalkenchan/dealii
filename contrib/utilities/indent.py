#!/usr/bin/env python
"""This script can be used to format code in external projects
(that using deal.II) by adding .clang_format files.

This program formats code using 'clang-format'.
If this program is executed on dry run mode, only the file names of
the files that are not formatted correctly are reported
without actually formatting them.

If this program is executed on dry run mode and if the code base is
correctly formatted, then the program doesn't write out anything.
This functionality can be exploited by a pre-commit git-hook
to check whether the codebase is formatted correctly.

Usage:
        python contrib/utilities/indent.py
"""

from __future__ import print_function

import argparse
import time
import distutils.spawn
import distutils.file_util

import filecmp
import fnmatch
import multiprocessing
import os
import logging
import Queue
import re
import shutil
import subprocess
import threading

from tempfile import mkdtemp, mkstemp


def parse_arguments():
    """
    Argument parser.
    """
    parser = argparse.ArgumentParser("Run clang-format on a list of files "
                                     "in a given list of directories "
                                     "having a given list of file extensions."
                                     "This program requires "
                                     "clang-format version 6.0.")

    parser.add_argument("-b", "--clang-format-binary", metavar="PATH",
                        default=distutils.spawn.find_executable("clang-format"))

    parser.add_argument("--regex", default="*.cc,*.h,*.cu,*.cuh",
                        help="Regular expression (regex) to filter files on "
                        "which clang-format is applied.")

    parser.add_argument("--dry-run", default=False, action='store_true',
                        help="If --dry-run is passed as an argument, "
                        "file names of files that are not formatted correctly "
                        "are written out, without actually formatting them.")

    parser.add_argument("-dirs", "--directories",
                        default="include,source,tests,examples",
                        help="Comma-delimited list of directories to work on."
                        "By default only \"examples\", \"include\", "
                        "\"source\" and \"tests\" "
                        "directories are chosen to work on.")

    parser.add_argument("-j", metavar="THREAD_COUNT", type=int, default=0,
                        help="Number of clang-format instances to be run "
                        "in parallel."
                        "By default this is equal to the maximum number of "
                        "available threads less one.")

    return parser.parse_args()


def check_clang_format_version(clang_format_binary, compatible_version_list):
    """
    Check whether clang-format with suitable version is installed.

    Keyword arguments:
    clang_format_binary     -- path of the installed clang format binary
    compatible_version_list -- a list of compatible clang-format versions
    """
    if clang_format_binary:
        try:
            clang_format_version = subprocess.check_output([clang_format_binary,
                                                            '--version'])
            version_number = re.search(r'Version\s*([\d.]+)',
                                       clang_format_version,
                                       re.IGNORECASE).group(1)
            if version_number not in compatible_version_list:
                logging.error(
                    """
                    ***
                    ***   No compatible clang-format program found.
                    ***
                    ***   Install any of the following versions
                    ***""" ' '.join(compatible_version_list)
                )
        except subprocess.CalledProcessError as subprocess_error:
            logging.error(subprocess_error)
            raise
    else:
        logging.error(
            """
            ***
            ***   No clang-format program found.
            ***
            ***   You can run
            ***       'contrib/utilities/download_clang_format'
            ***   or
            ***       'contrib/utilities/compile_clang_format'
            ***   to install a compatible binary into 'contrib/utilities/programs'.
            ***
            """
        )


def format_file(parsed_arguments, task_queue, temp_dir):
    """
    A given thread worker takes out sourcecode files, one at a time,
    out of the task_queue and tries to apply clang-format to format code on them.
    Each thread continuously attempts to empty the task_queue.
    If dry-run is switched on, only report the file names of files that
    are found with incorrect formatting without overriding them.

    Arguments:
    parsed_arguments           -- arguments provided to this program
    task_queue     -- a queue of sourcecode files (or file names) to be formatted
    full_file_name -- the file name of the file to be formatted/indented
    temp_dir       -- temporary directory to dump temporary files used to diff
    """
    while True:
        #
        # Get a file name from the list of sourcecode files in task_queue
        #
        full_file_name = task_queue.get()
        #
        # Get file name ignoring full path of the directory its in.
        #
        file_name = os.path.basename(full_file_name)
        #
        # Generate a temporary file and copy the contents of the given file.
        #
        _, temp_file_name = mkstemp(dir=temp_dir,
                                    prefix=file_name+'.',
                                    suffix='.tmp')

        shutil.copyfile(full_file_name, temp_file_name)
        #
        # Prepare command line statement to be executed by a subprocess call
        # to apply formatting to file_name.
        #
        apply_clang_format_str = parsed_arguments.clang_format_binary + ' ' + \
            full_file_name + " > " + temp_file_name
        try:
            subprocess.call(apply_clang_format_str, shell=True)
        except OSError as os_error:
            logging.error(os_error)
            raise
        except subprocess.CalledProcessError as subprocess_error:
            logging.error(subprocess_error)
            raise
        #
        # Compare the original file and the formatted file from clang-format.
        # If it's a dry run and if files differ, write out that the original file
        # is not formatted correctly.
        # Otherwise override the original file with formatted content.
        #
        if not filecmp.cmp(full_file_name, temp_file_name):
            if parsed_arguments.dry_run:
                print (full_file_name, " - file indented incorrectly")
                os.remove(temp_file_name)
            else:
                shutil.move(temp_file_name, full_file_name)
        #
        # Indicate that the current file name is processed by the current thread.
        # Once task_done() is called by a thread, the total count of
        # unfinished tasks goes down by one.
        #
        task_queue.task_done()


def process(arguments):
    """
    Collect all files found in the directories list matching with
    a given regex (regular expression) with n_threads number of threads
    in parallel.
    """
    tmpdir = mkdtemp()

    n_threads = arguments.j
    n_available_threads = multiprocessing.cpu_count()
    #
    # If not specified, n_threads is equal to the maximum number of
    # available threads less one.
    #
    if n_threads == 0:
        n_threads = (n_available_threads-1) if n_available_threads > 1 else 1

    logging.info("Number of threads picked up: %d", n_threads)

    #
    # Create n_threads number of queues, one for each thread.
    #
    task_queue = Queue.Queue(n_threads)

    #
    # Start n_threads number of thread workers that will execute
    # a target with given arguments.
    #
    for _ in range(n_threads):
        thread_worker = threading.Thread(target=format_file,
                                         args=(arguments, task_queue, tmpdir))
        thread_worker.daemon = True
        thread_worker.start()

    #
    # Gather all the files that are needed to be formatted in task_queue.
    # Look through all directories, recursively, and find all files
    # that match the given regex.
    #
    for directory in arguments.directories.split(','):
        for dirpath, _, filenames in os.walk(directory):
            for pattern in arguments.regex.split(','):
                for file_name in fnmatch.filter(filenames, pattern):
                    task_queue.put(os.path.join(dirpath, file_name))
    #
    # Blocks (some) threads until all the threads finished their tasks.
    # Works similar to MPI_Barrier().
    # In other words, threads wait until all the tasks in task_queue
    # have finshed.
    #
    task_queue.join()

    shutil.rmtree(tmpdir)


if __name__ == "__main__":
    START = time.time()
    PARSED_ARGUMENTS = parse_arguments()

    #
    # If clang-format-binary is not found, search again in
    # contrib/utlitlies/programs/clang-6/bin
    #
    if not PARSED_ARGUMENTS.clang_format_binary:
        os.environ["PATH"] += ':' + \
            os.getcwd() + "/contrib/utilities/programs/clang-6/bin"
        PARSED_ARGUMENTS.clang_format_binary = distutils.spawn.find_executable(
            "clang-format")

    #
    # Do not log verbose information on dry-run.
    #
    if PARSED_ARGUMENTS.dry_run:
        logging.basicConfig(level=logging.WARNING)
    else:
        logging.basicConfig(level=logging.INFO)

    check_clang_format_version(PARSED_ARGUMENTS.clang_format_binary,
                               ['6.0.0', '6.0.1'])
    process(PARSED_ARGUMENTS)
    FINISH = time.time()

    logging.info("Finished code formatting in: %f seconds.", (FINISH-START))
