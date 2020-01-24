# Author: Victor Kich
# Github: https://github.com/victorkich
# E-mail: victorkich@yahoo.com.br

from matplotlib import pyplot as plt
from mpl_toolkits import mplot3d
from matplotlib.animation import FuncAnimation
import math
import numpy as np
import pandas as pd
import time
import threading
import random

pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)

def deg2rad(deg):
    ''' Convert angles from degress to radians
    '''
    return np.pi * deg / 180.0

def rad2deg(rad):
    ''' Converts angles from radians to degress
    '''
    return 180.0 * rad / np.pi

def dh(a, alfa, d, theta):
    ''' Builds the Homogeneous Transformation matrix
        corresponding to each line of the Denavit-Hartenberg
        parameters
    '''
    m = np.array([
        [np.cos(theta), -np.sin(theta)*np.cos(alfa),
        np.sin(theta)*np.sin(alfa), a*np.cos(theta)],
        [np.sin(theta), np.cos(theta)*np.cos(alfa),
        -np.cos(theta)*np.sin(alfa), a*np.sin(theta)],
        [0, np.sin(alfa), np.cos(alfa), d],
        [0, 0, 0, 1]
    ])
    return m

class ArmRL(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

        self.zeros = np.array([210.0, 180.0, 65.0, 153.0])
        self.goals = np.array([0.0 for i in range(4)])
        self.plotpoints = False

    def run(self):
        rt = threading.Thread(name = 'realtime', target = self.realtime)
        rt.setDaemon(True)
        rt.start()
        obj = threading.Thread(name = 'objectives', target = self.objectives)
        obj.setDaemon(True)
        obj.start()

        goals = np.array([0, 355, 0, 0])
        self.ctarget(goals, 300)

        goals = np.array([0, 0, 0, 0])
        self.ctarget(goals, 200)

    def objectives(self):
        while True:
            obj_number = np.random.randint(low=5, high=40, size=1)
            self.points = []
            self.points.append([51.3, 0, 0])
            cont = 0
            while cont < obj_number:
                rands = [random.uniform(-55.6, 55.6) for i in range(3)]
                if rands[2] >= 0:
                    if abs(rands[0]) >= abs(rands[1]):
                        value = math.sqrt(rands[0]**2 + rands[2]**2)
                    else:
                        value = math.sqrt(rands[1]**2 + rands[2]**2)
                    if value <= 55.6:
                        self.points.append(rands)
                        cont = cont + 1
            self.points = pd.DataFrame(self.points)
            self.points.rename(columns = {0:'x', 1:'y', 2:'z'}, inplace=True)
            print(self.points)
            self.plotpoints = True
            while True:
                for p in range(int(obj_number)):
                    validation_test = []
                    for a in range(3):
                        if(math.isclose(self.df.iat[3, a], self.points.iat[p, a],\
                                        abs_tol=0.5)):
                            validation_test.append(True)
                        else:
                            validation_test.append(False)
                    if all(validation_test):
                        self.points.drop(p, inplace=True)
                time.sleep(0.01)

    def fk(self, mode):
        ''' Forward Kinematics
        '''
        # Convert angles from degress to radians
        t = [deg2rad(x) for x in self.goals]
        # Register the DH parameters
        hs = []
        hs.append(dh(0,       -np.pi/2, 4.3,  t[0]))
        if mode >= 2:
            hs.append(dh(0,    np.pi/2, 0.0,  t[1]))
        if mode >= 3:
            hs.append(dh(0,   -np.pi/2, 24.3, t[2]))
        if mode == 4:
            hs.append(dh(27.0, np.pi/2, 0.0,  t[3] - np.pi/2))

        m = np.eye(4)
        for h in hs:
            m = m.dot(h)
        return m

    def ik(self):
        return False

    def realtime(self):
        while True:
            # Modes -> 1 = first joint / 2 = second joint
            #          3 = third joint / 4 = fourth joint
            df = pd.DataFrame(np.zeros(3)).T
            df2 = pd.DataFrame(self.fk(mode=i)[0:3, 3] for i in range(2,5))
            df = df.append(df2).reset_index(drop=True)
            df.rename(columns = {0:'x', 1:'y', 2:'z'}, inplace=True)
            self.df = df
            time.sleep(0.1)

    def ctarget(self, targ, iterations):
        self.stop = False
        dtf = threading.Thread(name = 'teste',target = self.dataFlow,\
                               args = (targ, iterations, ))
        dtf.setDaemon(True)
        dtf.start()
        while True:
            if self.stop == True:
                break
            time.sleep(0.1)

    def dataFlow(self, targ, iterations):
        track = np.linspace(self.goals, targ, num=iterations)
        for t in track:
            self.goals = t
            #print(t)
            time.sleep(0.1)
        self.stop = True

arm = ArmRL()
fig = plt.figure()
ax = plt.gca(projection='3d')

def animate(i):
    x, y, z = [np.array(i) for i in [arm.df.x, arm.df.y, arm.df.z]]
    ax.clear()
    ax.plot3D(x, y, z, 'gray', label='Links', linewidth=5)
    ax.scatter3D(x, y, z, color='black', label='Joints')
    ax.scatter(x[3], y[3], zs=0, zdir='z', label='Projection', color='red')
    ax.scatter3D(0, 0, 4.3, plotnonfinite=True, s=155000, norm=1, alpha=0.2, lw=0)

    if arm.plotpoints == True:
        x, y, z = [np.array(i) for i in [arm.points.x, arm.points.y, arm.points.z]]
        ax.scatter3D(x, y, z, color='green', label='Objectives')

    ax.legend(loc=2, prop={'size':10})
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_zlabel('z')
    ax.set_xlim([-60, 60])
    ax.set_ylim([-60, 60])
    ax.set_zlim([0, 60])

ani = FuncAnimation(fig, animate, interval=1)
arm.start()
plt.show()
