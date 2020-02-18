# Author: Victor Augusto Kich
# Github: https://github.com/victorkich
# E-mail: victorkich@yahoo.com.br

import numpy as np
import tensorflow as tf
from datetime import datetime
import environment
import threading
import fkmath as fkm

tf.compat.v1.disable_eager_execution()

def mlp(x, hidden_layers, output_layer, activation=tf.tanh, last_activation=None):
    ''' Multi-layer perceptron
    '''
    for l in hidden_layers:
        x = tf.compat.v1.layers.dense(x, units=l, activation=activation)
    return tf.compat.v1.layers.dense(x, units=output_layer, activation=last_activation)

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

def gaussian_log_likelihood(x, mean, log_std):
    ''' Gaussian Log Likelihood
    '''
    log_p = -0.5 *((x-mean)**2 / (tf.exp(log_std)**2+1e-9) + 2*log_std + np.log(2*np.pi))
    return tf.reduce_sum(log_p, axis=-1)

class Buffer():
    ''' Class to store the experience from a unique policy
    '''
    def __init__(self, gamma=0.99, lam=0.95):
        self.gamma = gamma
        self.lam = lam
        self.adv = []
        self.ob = []
        self.ac = []
        self.rtg = []

    def store(self, temp_traj, last_sv):
        ''' Add temp_traj values to the buffers and compute the advantage and reward to go
            Parameters:
            -----------
            temp_traj: list where each element is a list that contains:
                       observation, reward, action, state-value
            last_sv: value of the last state (Used to Bootstrap)
        '''
        # store only if there are temporary trajectories
        if len(temp_traj) > 0:
            self.ob.extend(temp_traj[:,0])
            rtg = discounted_rewards(temp_traj[:,1], last_sv, self.gamma)
            self.adv.extend(GAE(temp_traj[:,1], temp_traj[:,3], last_sv, self.gamma, self.lam))
            self.rtg.extend(rtg)
            self.ac.extend(temp_traj[:,2])

    def get_batch(self):
        # standardize the advantage values
        norm_adv = (self.adv - np.mean(self.adv)) / (np.std(self.adv) + 1e-10)
        return np.array(self.ob), np.array(self.ac), np.array(norm_adv), np.array(self.rtg)

    def __len__(self):
        assert(len(self.adv) == len(self.ob) == len(self.ac) == len(self.rtg))
        return len(self.ob)

def PPO(environment=None, hidden_sizes=[32], cr_lr=5e-3, ac_lr=5e-3, num_epochs=50, \
        minibatch_size=5000, gamma=0.99, lam=0.95, eps=0.1, actor_iter=5,\
        critic_iter=10, steps_per_env=100):

    # Placeholders
    act_dim = 4
    obs_dim = 4
    low_action_space = 0
    high_action_space = 105
    act_ph = tf.compat.v1.placeholder(shape=(None, act_dim), dtype=tf.float32, name='act')
    obs_ph = tf.compat.v1.placeholder(shape=(None, obs_dim), dtype=tf.float32, name='obs')
    ret_ph = tf.compat.v1.placeholder(shape=(None,), dtype=tf.float32, name='ret')
    adv_ph = tf.compat.v1.placeholder(shape=(None,), dtype=tf.float32, name='adv')
    old_p_log_ph = tf.compat.v1.placeholder(shape=(None,), dtype=tf.float32, name='old_p_log')

    # Computational graph for the policy of a continuous action space
    with tf.compat.v1.variable_scope('actor_nn'):
        p_logits = mlp(obs_ph, hidden_sizes, act_dim, tf.tanh, last_activation=tf.tanh)
        log_std = tf.compat.v1.get_variable(name='log_std', initializer=np.zeros(act_dim, dtype=np.float32)-0.5)

    # Add noise to the mean values predicted
    # The noise is proportional to the standard deviation
    p_noisy = p_logits + tf.random.normal(tf.shape(p_logits), 0, 1) * tf.exp(log_std)
    # CLip the noisy actions
    act_smp = tf.clip_by_value(p_noisy, low_action_space, high_action_space)

    # Compute the gaussian log likelihood
    p_log = gaussian_log_likelihood(act_ph, p_logits, log_std)

    # Neural network value function approximizer
    with tf.compat.v1.variable_scope('critic_nn'):
        s_values = mlp(obs_ph, hidden_sizes, 1, tf.tanh, last_activation=None)
        s_values = tf.squeeze(s_values)

    # PPO loss function
    p_loss = clipped_surrogate_obj(p_log, old_p_log_ph, adv_ph, eps)
    # MSE loss function
    v_loss = tf.reduce_mean((ret_ph - s_values)**2)

    # Policy optimizer
    p_opt = tf.compat.v1.train.AdamOptimizer(ac_lr).minimize(p_loss)
    # Value function optimizer
    v_opt = tf.compat.v1.train.AdamOptimizer(cr_lr).minimize(v_loss)

    # Time
    now = datetime.now()
    clock_time = "{}_{}.{}.{}".format(now.day, now.hour, now.minute, now.second)
    print('Time: ', clock_time)

    # Create a session
    sess = tf.compat.v1.Session()
    # Initialize the variables
    sess.run(tf.compat.v1.global_variables_initializer())

    # Variables to store the total number of steps ahs epochs
    step_count = 0
    epoch_count = 0

    for ep in range(num_epochs):
        # Create the buffer that will contain the trajectories (full or partial)
        # Run with the last policy
        buffer = Buffer(gamma, lam)
        # Lists to store rewards and length of the trajectories completed
        batch_rew = []
        batch_len = []
        temp_buf = []
        epoch_count += 1

        for _ in range(steps_per_env):
            step_count += 1

            # Iterate over a fixed number of steps
            print("             -=============- Epoch: ", epoch_count,\
                    " Step: ", step_count, " -=============-")
            act, val = sess.run([act_smp, s_values], feed_dict={obs_ph:[env.n_obs]})
            act = np.squeeze(act)

            # Take a step in the environment
            obs2, rew, done = env.step(act, epoch_count, step_count)
            print("Reward: ", rew)

            # Add the new transition to the temporary buffers
            temp_buf.append([env.n_obs.copy(), rew, act, np.squeeze(val)])

            env.n_obs = obs2.copy()

            if done:
                # Store the full trajectory in the buffer
                # (the value of the last state is 0 as the trajectory is completed)
                buffer.store(np.array(temp_buf), 0)

                # Empty temporary buffer
                temp_buf = []

                batch_rew.append(env.get_episode_reward())
                batch_len.append(env.get_episode_length())

                # Reset the environment
                env.reset()

        # Bootstrap with the estimated state value of the next state!
        last_v = sess.run(s_values, feed_dict={obs_ph:[env.n_obs]})
        buffer.store(np.array(temp_buf), np.squeeze(last_v))

        # Gather the entire batch from the buffer
        # NB: all the batch is used and deleted after the optimization.
        # That is because PPO is on-policy.
        obs_batch, act_batch, adv_batch, rtg_batch = buffer.get_batch()

        old_p_log = sess.run(p_log, feed_dict={obs_ph:obs_batch, act_ph:act_batch,\
                             adv_ph:adv_batch, ret_ph:rtg_batch})
        old_p_batch = np.array(old_p_log)

        lb = len(buffer)
        shuffled_batch = np.arange(lb)

        # Policy optimization steps
        for _ in range(actor_iter):
            # Shuffle the batch on every iteration
            np.random.shuffle(shuffled_batch)
            for idx in range(0, lb, minibatch_size):
                minib = shuffled_batch[idx:min(idx+minibatch_size, lb)]
                sess.run(p_opt, feed_dict={obs_ph:obs_batch[minib],\
                         act_ph:act_batch[minib], adv_ph:adv_batch[minib],\
                         old_p_log_ph:old_p_batch[minib]})

        # Value function optimization steps
        for _ in range(critic_iter):
            # Shuffle the batch on every iteration
            np.random.shuffle(shuffled_batch)
            for idx in range(0, lb, minibatch_size):
                minib = shuffled_batch[idx:min(idx+minibatch_size, lb)]
                sess.run(v_opt, feed_dict={obs_ph:obs_batch[minib],\
                         ret_ph:rtg_batch[minib]})

        # Print some statistics and run the summary for visualizing it on TB
        if len(batch_rew) > 0:
            print('Ep:%d Rew:%.2f -- Step:%d' % (ep, np.mean(batch_rew), step_count))

        env.clear_tratectory()

if __name__ == '__main__':
    env = environment.arm()
    env.start()
    # (env, hidden_sizes=[64,64], cr_lr=5e-4, ac_lr=2e-4, num_epochs=5000,
    # minibatch_size=256, gamma=0.99, lam=0.95, eps=0.15, actor_iter=6,
    # critic_iter=10, steps_per_env=5000)
    ppo = threading.Thread(name = 'PPO', target = PPO, args = (env, [32,32],\
                           5e-4, 2e-4, 5000, 128, 0.99, 0.95, 0.15, 6, 10, 100))
    ppo.setDaemon(True)
    ppo.start()
    environment.showPlot(env)
