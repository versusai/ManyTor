# Author: Victor Augusto Kich
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
import tensorflow as tf
from datetime import datetime

pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)

def mlp(x, hidden_layers, output_layer, activation=tf.tanh, last_activation=None):
    ''' Multi-layer perceptron
    '''
    for l in hidden_layers:
        x = tf.layers.dense(x, units=l, activation=activation)
    return tf.layers.dense(x, units=output_layer, activation=last_activation)

def softmax_entropy(logits):
    ''' Softmax Entropy
    '''
    return -tf.reduce_sum(tf.nn.softmax(logits, axis=-1) * tf.nn.log_softmax(logits, axis=-1), axis=-1)

def clipped_surrogate_obj(new_p, old_p, adv, eps):
    ''' Clipped surrogate objective function
    '''
    rt = tf.exp(new_p - old_p) # i.e. pi / old_pi
    return -tf.reduce_mean(tf.minimum(rt*adv, tf.clip_by_value(rt, 1-eps, 1+eps)*adv))

def GAE(rews, v, v_last, gamma=0.99, lam=0.95):
    ''' Generalized Advantage Estimation
    '''
    assert len(rews) == len(v)
    vs = np.append(v, v_last)
    delta = np.array(rews) + gamma*vs[1:] - vs[:-1]
    gae_advantage = discounted_rewards(delta, 0, gamma*lam)
    return gae_advantage

def discounted_rewards(rews, last_sv, gamma):
    ''' Discounted reward to go
        Parameters:
        ----------
        rews: list of rewards
        last_sv: value of the last state
        gamma: discount value
    '''
    rtg = np.zeros_like(rews, dtype=np.float32)
    rtg[-1] = rews[-1] + gamma*last_sv
    for i in reversed(range(len(rews)-1)):
        rtg[i] = rews[i] + gamma*rtg[i+1]
    return rtg

#-------------------------------------------------------------------------------

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
        self.trajectory = pd.DataFrame({'x':[], 'y':[], 'z':[]})
        self.obj_number = 0

    def run(self):
        rt = threading.Thread(name = 'realtime', target = self.realtime)
        rt.setDaemon(True)
        rt.start()

        obj = threading.Thread(name = 'objectives', target = self.objectives)
        obj.setDaemon(True)
        obj.start()

        goals = np.array([-50, 50, 150, -60])
        self.ctarget(goals, 250)

    def objectives(self):
        while True:
            self.obj_number = np.random.randint(low=5, high=40, size=1)
            self.points = []
            self.points.append([51.3, 0, 0])
            cont = 0
            while cont < self.obj_number:
                rands = [random.uniform(-51.3, 51.3) for i in range(3)]
                if rands[2] >= 0:
                    value = math.sqrt(math.sqrt(rands[0]**2 + rands[1]**2)**2 + rands[2]**2)
                    if value <= 51.3:
                        self.points.append(rands)
                        cont = cont + 1
            self.points = pd.DataFrame(self.points)
            self.points.rename(columns = {0:'x', 1:'y', 2:'z'}, inplace=True)
            print(self.points)
            self.plotpoints = True
            while True:
                for p in range(int(self.obj_number)):
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
            self.trajectory = self.trajectory.append(self.df.iloc[3])
            self.trajectory.drop_duplicates(inplace=True)

            distance = pd.DataFrame({'obj_dist':[]})
            for p in range(int(self.obj_number)):
                x, y, z = [(abs(self.df.iloc[3, i] - self.points.iloc[p, i]))\
                           for i in range(3)]
                dist = pd.DataFrame({'obj_dist':[math.sqrt(math.sqrt(x**2 + y**2)**2 + z**2)]})
                distance = distance.append(dist).reset_index(drop=True)
            print(distance)
            time.sleep(0.1)

    def ctarget(self, targ, iterations):
        self.stop = False
        dtf = threading.Thread(name = 'dataflow',target = self.dataFlow,\
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
    ax.scatter3D(0, 0, 4.3, plotnonfinite=False, s=135000, norm=1, alpha=0.2, lw=0)
    x, y, z = [np.array(i) for i in [arm.trajectory.x, arm.trajectory.y, arm.trajectory.z]]
    ax.plot3D(x, y, z, c='b', label='Trajectory')

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
