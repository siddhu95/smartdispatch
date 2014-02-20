#!/usr/bin/env python
import os
import argparse
import datetime
import numpy as np
from subprocess import check_output


availableQueues = {
    'qtest@mp2': {'coresPerNode': 24, 'maxWalltime': '00:01:00:00'},
    'qwork@mp2': {'coresPerNode': 24, 'maxWalltime': '05:00:00:00'},
    'qfbb@mp2': {'coresPerNode': 288, 'maxWalltime': '05:00:00:00'},
    'qfat256@mp2': {'coresPerNode': 48, 'maxWalltime': '05:00:00:00'},
    'qfat512@mp2': {'coresPerNode': 48, 'maxWalltime': '02:00:00:00'},

    'qtest@ms': {'coresPerNode': 8, 'maxWalltime': '00:01:00:00'},
    'qwork@ms': {'coresPerNode': 8, 'maxWalltime': '05:00:00:00'},
    'qlong@ms': {'coresPerNode': 8, 'maxWalltime': '41:16:00:00'},

    # 'qwork@brume' : {'coresPerNode' : 0, 'maxWalltime' : '05:00:00:00'} # coresPerNode is variable and not relevant for this queue
}


def main():
    args = parseArguments()

    # list_commandAndOptions must be a list of lists
    list_commandAndOptions = []
    for opt in args.commandAndOptions:
        opt_split = opt.split()
        for i, split in enumerate(opt_split):
            opt_split[i] = os.path.normpath(split)  # If the arg value is a path, remove the final '/' if there is one at the end.
        list_commandAndOptions += [opt_split]

    subPathLogs, pathQsubFolder = createJobsFolder(list_commandAndOptions)

    list_jobs_str, list_jobsOutput_folderName = unfoldJobs(list_commandAndOptions)

    # Distribute equally the jobs among the QSUB files and generate those files
    nbJobsTotal = len(list_jobs_str)
    nbQsubFiles = int(np.ceil(nbJobsTotal / float(args.jobsPerNode)))
    nbJobPerFile = int(np.ceil(nbJobsTotal / float(nbQsubFiles)))

    qsubFilesToLaunch = []
    for i in range(nbQsubFiles):
        start = i * nbJobPerFile
        end = (i + 1) * nbJobPerFile
        if end > nbJobsTotal:
            end = nbJobsTotal
        qsubFileName = os.path.join(pathQsubFolder, 'jobCommands_' + str(i) + '.sh')
        writeQsubFile(list_jobs_str[start:end], list_jobsOutput_folderName[start:end], qsubFileName, subPathLogs, args.queueName, args.walltime, os.getcwd(), args.cuda)
        qsubFilesToLaunch += [qsubFileName]

    # Launch the jobs with QSUB
    if not args.doNotLaunchJobs:
        for qsubFileName in qsubFilesToLaunch:
            qsub_output = check_output('qsub ' + qsubFileName, shell=True)
            print qsub_output,


def parseArguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('-q', '--queueName', required=True, help='Queue used (ex: qwork@mp2, qfat256@mp2, qfat512@mp2)')
    parser.add_argument('-t', '--walltime', required=False, help='Set the estimated running time of your jobs using the DD:HH:MM:SS format. Note that they will be killed when this time limit is reached.')
    parser.add_argument('-n', '--jobsPerNode', type=int, required=False, help='Set the number of jobs per nodes.')
    parser.add_argument('-c', '--cuda', action='store_true', help='Load CUDA before executing your code.')
    parser.add_argument('-x', '--doNotLaunchJobs', action='store_true', help='Creates the QSUB files without launching them.')
    parser.add_argument("commandAndOptions", help="Options for the command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    # Check for invalid arguments
    if len(args.commandAndOptions) < 1:
        parser.error("You need to specify a command to launch.")
    if args.queueName not in availableQueues and (args.jobsPerNode is None or args.walltime is None):
        parser.error("Unknown queue, --jobsPerNode and --walltime must be set.")

    # Set queue defaults for non specified params
    if args.jobsPerNode is None:
        args.jobsPerNode = availableQueues[args.queueName]['coresPerNode']
    if args.walltime is None:
        args.walltime = availableQueues[args.queueName]['maxWalltime']
    return args


def unfoldJobs(list_commandAndOptions):
    list_jobs_str = ['']
    list_jobsOutput_folderName = ['']

    for argument in list_commandAndOptions:
        list_jobs_tmp = []
        list_folderName_tmp = []
        for valueForArg in argument:
            for job_str, folderName in zip(list_jobs_str, list_jobsOutput_folderName):
                list_jobs_tmp += [job_str + valueForArg + ' ']
                valueForArg_tmp = valueForArg[-30:].split('/')[-1]  # Deal with path as parameter
                list_folderName_tmp += [valueForArg_tmp] if folderName == '' else [folderName + '-' + valueForArg_tmp]
        list_jobs_str = list_jobs_tmp
        list_jobsOutput_folderName = list_folderName_tmp
    return list_jobs_str, list_jobsOutput_folderName


def createJobsFolder(list_commandAndOptions):
    pathLogs = os.path.join(os.getcwd(), 'LOGS_QSUB')

    # Creating the folder in 'LOGS_QSUB' where the results will be saved
    nameFolderSavingLogs = ''
    for argument in list_commandAndOptions:
        str_tmp = argument[0][-30:] + ('' if len(argument) == 1 else ('-' + argument[-1][-30:]))
        str_tmp = str_tmp.split('/')[-1]  # Deal with path as parameter
        nameFolderSavingLogs += str_tmp if nameFolderSavingLogs == '' else ('__' + str_tmp)
    current_time = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    nameFolderSavingLogs = current_time + '___' + nameFolderSavingLogs[:220]  # No more than 256 character
    subPathLogs = os.path.join(pathLogs, nameFolderSavingLogs)
    if not os.path.exists(subPathLogs):
        os.makedirs(subPathLogs)

    # Creating the folder where the QSUB files will be saved
    pathQsubFolder = os.path.join(subPathLogs, 'QSUB_commands')
    if not os.path.exists(pathQsubFolder):
        os.makedirs(pathQsubFolder)
    return subPathLogs, pathQsubFolder


def writeQsubFile(list_jobs_str, list_jobsOutput_folderName, qsubFileName, subPathLogs, queue, walltime, currentDir, useCuda):
    """
    Example of a line for one job for QSUB:
        cd $SRC ; python -u trainAutoEnc2.py 10 80 sigmoid 0.1 vocKL_sarath_german True True > trainAutoEnc2.py-10-80-sigmoid-0.1-vocKL_sarath_german-True-True &
    """
    # Creating the file that will be launch by QSUB
    with open(qsubFileName, 'w') as qsubJobFile:
        qsubJobFile.write('#!/bin/bash\n')
        qsubJobFile.write('#PBS -q ' + queue + '\n')
        qsubJobFile.write('#PBS -l nodes=1:ppn=1\n')
        qsubJobFile.write('#PBS -V\n')
        qsubJobFile.write('#PBS -l walltime=' + walltime + '\n\n')

        if useCuda:
            qsubJobFile.write('module load cuda\n')
        qsubJobFile.write('SRC_DIR_SMART_LAUNCHER=' + currentDir + '\n\n')

        jobTemplate = "cd $SRC_DIR_SMART_LAUNCHER; {} &> {} &\n"
        for job, folderName in zip(list_jobs_str, list_jobsOutput_folderName):
            qsubJobFile.write(jobTemplate.format(job, os.path.join(subPathLogs, folderName)))

        qsubJobFile.write('\nwait\n')


if __name__ == "__main__":
    main()