#!/usr/bin/python
# coding=utf-8
import paramiko
import os
import argparse
import os
import re
import io

REMOTE_HOME = "/var/www/html/update/"
REMOTE_HOME_TEST = "/var/www/html/update_test/"

parser = argparse.ArgumentParser(description='更新包打包软件')
parser.add_argument('-ip'           , default="111.111.111.111", help="ip")
parser.add_argument('-port'         , default=22, help="端口" , type=int )
parser.add_argument('-username'     , default="xxx", help="登录名")
parser.add_argument('-password'     , default="xxx", help="密码")
#parser.add_argument('-remoteRoot'   , default=REMOTE_HOME, help="远程服务器的主目录")
parser.add_argument("-localRoot"    , default="../../updateFile/", help = "本地的主目录")
parser.add_argument("-platform"     , default="android" , help = "指定的平台")
parser.add_argument("-svnVersion"   , help = "指定的svn版本号")
parser.add_argument("-svnVersionFile", help = "指定的svn版本文件")
parser.add_argument("-test"         , action = "store_true", help = "指定的svn版本文件")

userArgs = parser.parse_args()

if userArgs.localRoot[-1] != '/':
        userArgs.localRoot = userArgs.localRoot + "/"

def getSvnDiff(path):
    version = userArgs.svnVersion
    if not version:
        if userArgs.svnVersionFile:
            file = io.open(userArgs.svnVersionFile)
            version = file.read()
            file.close()
            version.strip()
    orgDir = os.getcwd()
    os.chdir(userArgs.localRoot + path)
    if version and version != "":
        data = os.popen('svn diff -r%s:HEAD --summarize' % version).readlines()
    else:
        data = os.popen('svn diff --summarize').readlines()
    os.chdir(orgDir)
    return data

class SFTPClient:
    def __init__(self , ip , port , username , password, remoteRoot):
        self.transport = paramiko.Transport(ip, port)
        self.remoteRoot = remoteRoot
        self.transport.connect(username=username, password=password)
        self.sftp = paramiko.SFTPClient.from_transport(self.transport)

    def uploadFile(self, localFile  , remoteFile):
        print 'upload file:\t%s' % (remoteFile)
        dir = ""
        remoteFile = remoteFile.replace("\\" , "/")
        for v in remoteFile.split("/")[0:-1]:
            dir = dir + "/" + v
            if not self.isExist(dir):
                print("create folder:" + dir)
                self.sftp.mkdir(self.remoteRoot + dir)
        self.sftp.put(localFile, self.remoteRoot + remoteFile)

    def downloadFile(self, remoteFile , localFile):
        self.sftp.get(self.remoteRoot + remoteFile, localFile)

    def __get_all_files_in_remote_dir(self, remote_dir):
        all_files = []

        if remote_dir[-1] == '/':
            remote_dir = remote_dir[0:-1]

        files = self.sftp.listdir_attr(self.remoteRoot + remote_dir)
        for x in files:
            filename = remote_dir + '/' + x.filename
            if str(x)[0] == "d":
                all_files.extend(self.__get_all_files_in_remote_dir(filename))
            else:
                all_files.append(filename)
        return all_files

    def downloadDir(self , remote_dir , local_dir):
        all_files = self.__get_all_files_in_remote_dir(remote_dir)
        for x in all_files:
            filename = x.split('/')[-1]
            local_filename = os.path.join(local_dir, x)
            print 'download file:\t%s' % x.split('/')[-1] 
            self.sftp.get(x, local_filename)
        
    def __get_all_files_in_local_dir(self, local_dir):
        all_files = []
        files = os.listdir(local_dir)
        for x in files:
            filename = os.path.join(local_dir, x)
            if os.path.isdir(x):
                all_files.extend(self.__get_all_files_in_local_dir(filename))
            else:
                all_files.append(filename)
        return all_files

    def uploadDir(self, local_dir , remote_dir):
        if remote_dir[-1] == '/':
            remote_dir = remote_dir[0:-1]
        all_files = self.__get_all_files_in_local_dir(local_dir)
        for x in all_files:
            remote_filename = self.remoteRoot + remote_dir + '/' + x
            self.uploadFile(x , remote_dir + '/' + x)

    def isExist(self, path):
        try:
            self.sftp.stat(self.remoteRoot + path)
            return True
        except IOError:
            return False

    def removeRemote(self , remote_path):
        if self.isExist(remote_path):
            st = self.sftp.stat(self.remoteRoot + remote_path)
            if str(st)[0] == "d":
                self.removeDir(remote_path)
            else:
                self.removeFile(remote_path)

    def removeFile(self , remote_file):
        if self.isExist(remote_file):
            print 'remove file:\t%s' % remote_file
            self.sftp.remove(self.remoteRoot + remote_file)

    def removeDir(self , remote_dir):
        if self.isExist(remote_dir):
            all_files = self.__get_all_files_in_remote_dir(remote_dir)
            for x in all_files:
                print 'remove file:\t%s' % x
                self.sftp.remove(self.remoteRoot + x)
            print("remove Folder:\t %s" % remote_dir)
            self.sftp.rmdir(self.remoteRoot + remote_dir)

    def __del__(self):
        self.transport.close()
if userArgs.test:
    remotePath = REMOTE_HOME_TEST
else:
    remotePath = REMOTE_HOME
client = SFTPClient(userArgs.ip, userArgs.port , userArgs.username , userArgs.password, remotePath + userArgs.platform + "/")
diffs = getSvnDiff(userArgs.platform)
for file in diffs:
    file = file.replace("\n" , "").replace("\\" , "/")
    list = file.split(" ")
    path = userArgs.localRoot + userArgs.platform + "/" + list[-1]
    if list[0] == "M":
        if os.path.exists(path):
            client.uploadFile(path , list[-1])
    elif list[0] == "A":
        if os.path.exists(path):
            # 文件夹不管
            if os.path.isdir(path):
                pass
            else:
                client.uploadFile(path , list[-1])
    elif list[0] == "D":
        client.removeRemote(list[-1])
