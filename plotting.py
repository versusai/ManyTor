from vispy.scene import visuals, SceneCanvas
from vispy import app, scene
import numpy as np
import threading
import socket
import json
import time
import sys

HOST = 'localhost'  # Server ip address
PORT = 5003  		# Server port


def receive_data(sock):
	global joints_coordinates
	global points
	global trajectory
	global env_number
	stop = False
	obj_number = 0

	while not stop:
		msg_byte, _ = udp.recvfrom(2048)
		msg_list = json.loads(msg_byte)
		msg = np.array(msg_list)

		if msg[2] == 2:
			stop = True
			app.quit()
			sock.close()
		elif msg[2] == 3:
			env_number = int(msg[0])
			obj_number = int(msg[1])
			joints_coordinates = [np.empty((4, 3)) for i in range(msg[0])]
			points = np.empty((msg[0], msg[1], 3))
			trajectory = [np.empty((1, 3)) for i in range(msg[0])]
		else:
			ide = int(msg[0])
			msg = msg.reshape(-1, 3)
			index = msg[0, :]
			joints_coordinates[ide] = msg[1:5, :]
			points[ide] = msg[5:5+obj_number, :]
			if index[2] == 1:
				trajectory[ide] = np.array([0.0, 0.0, 51.3])
			trajectory[ide] = np.vstack((trajectory[ide], msg[5+obj_number:, :]))
		

def update(ev):
	for i in range(env_number):
		#traject.set_data(trajectory, edge_color='w', face_color='blue', size=1)
		point.set_data(points[i], edge_color='w', face_color='green', size=3)
		joint.set_data(joints_coordinates[i], color='gray', marker_size=5, face_color='red', edge_width= 5, edge_color='white')


		'''
		x, y, z = [np.array(i) for i in [self.df.x, self.df.y, self.df.z]]
		self.ax.clear()
		self.ax.plot3D(x, y, z, 'gray', label='Links', linewidth=5)
		self.ax.scatter3D(x, y, z, color='black', label='Joints')
		self.ax.scatter3D(x[3], y[3], zs=0, zdir='z', label='Projection', color='red')
		#self.ax.scatter3D(0, 0, 4.3, plotnonfinite=False, s=135000, norm=1, alpha=0.2, lw=0)
		x, y, z = [np.array(i) for i in [self.trajectory.x, self.trajectory.y, self.trajectory.z]]
		self.ax.plot3D(x, y, z, c='b', label='Trajectory')
	
		if self.plotpoints == True:
			x, y, z, = [], [], []
			n_x, n_y, n_z = [np.array(i) for i in [self.points.x, self.points.y, self.points.z]]
			for i in range(self.obj_number[0]):
				if self.boolplot[i]:
					x.append(n_x[i])
					y.append(n_y[i])
					z.append(n_z[i])
	
			legend = 'Objectives: ' + str(self.obj_remaining[0]) + '/' + str(self.obj_number[0])
			self.ax.scatter3D(x, y, z, color='green', label=legend)
	
		title = 'Epoch: ' + str(self.actual_epoch) + ' Step: ' + str(self.actual_step)
		self.ax.set_title(title, size=10)
		self.ax.legend(loc=2, prop={'size':7})
		self.ax.set_xlabel('x')
		self.ax.set_ylabel('y')
		self.ax.set_zlabel('z')
		self.ax.set_xlim([-60, 60])
		self.ax.set_ylim([-60, 60])
		self.ax.set_zlim([0, 60])
		'''
	
	
udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
orig = (HOST, PORT)
udp.bind(orig)

env_number = 1
joints_coordinates = np.empty((1, 4, 3))
points = np.empty((1, 1, 3))
trajectory = np.array((1, 1, 3))

dfs = threading.Thread(name='data_from_socket', target=receive_data, args=(udp, ))
dfs.setDaemon(True)
dfs.start()

canvas = SceneCanvas(show=True, size=(800, 600), resizable=False, keys="interactive")

view = canvas.central_widget.add_view()
# view.camera = 'turntable'
camera = scene.cameras.TurntableCamera(fov=60)
camera.set_range((-4, 4), (-4, 4), (-4, 4))
view.camera = camera
# xax = scene.Axis()
axis = visuals.XYZAxis(parent=view.scene)
# grid = visuals.GridLines(parent=view.scene)

point = visuals.Markers()
joint = visuals.LinePlot()
traject = visuals.Markers()

view.add(point)
view.add(joint)
view.add(axis)
view.add(traject)

timer = app.Timer()
timer.connect(update)
timer.start()

if __name__ == '__main__':
	canvas.show()
	canvas.app.reuse()
	time.sleep(0.2)
	if sys.flags.interactive == 0:
		app.run()
	print('FIM')
