import numpy as np


def multitask_rollout(
    env,
    agent,
    max_path_length=np.inf,
    render=False,
    render_kwargs=None,
    observation_key=None,
    desired_goal_key=None,
    representation_goal_key=None,
    get_action_kwargs=None,
    return_dict_obs=False,
):
    if render_kwargs is None:
        render_kwargs = {}
    if get_action_kwargs is None:
        get_action_kwargs = {}
    dict_obs = []
    dict_next_obs = []
    observations = []
    actions = []
    rewards = []
    terminals = []
    agent_infos = []
    env_infos = {}
    next_observations = []
    path_length = 0
    agent.reset()
    o = env.reset()
    if render:
        env.render(**render_kwargs)
    desired_goal = o[desired_goal_key]
    while path_length < max_path_length:
        dict_obs.append(o)
        if observation_key:
            s = o[observation_key]
        g = o[representation_goal_key]
        new_obs = np.hstack((s, g))
        a, agent_info = agent.get_action(new_obs, **get_action_kwargs)
        next_o, r, d, env_info = env.step(a)
        if render:
            env.render(**render_kwargs)
        observations.append(o)
        rewards.append(r)
        terminals.append(d)
        actions.append(a)
        next_observations.append(next_o)
        dict_next_obs.append(next_o)
        agent_infos.append(agent_info)
        if not env_infos:
            for k, v in env_info.items():
                env_infos[k] = [v]
        else:
            for k, v in env_info.items():
                env_infos[k].append(v)
        path_length += 1
        if d:
            break
        o = next_o
    actions = np.array(actions)
    if len(actions.shape) == 1:
        actions = np.expand_dims(actions, 1)
    observations = np.array(observations)
    next_observations = np.array(next_observations)
    if return_dict_obs:
        observations = dict_obs
        next_observations = dict_next_obs
    for k, v in env_infos.items():
        env_infos[k] = np.array(v)
    return dict(
        observations=observations,
        actions=actions,
        rewards=np.array(rewards).reshape(-1, 1),
        next_observations=next_observations,
        terminals=np.array(terminals).reshape(-1, 1),
        agent_infos=agent_infos,
        env_infos=env_infos,
        desired_goals=np.repeat(desired_goal[None], path_length, 0),
        full_observations=dict_obs,
    )


def multiagent_multitask_rollout(
    env,
    agent,
    max_path_length=np.inf,
    render=False,
    render_kwargs=None,
    observation_key=None,
    achieved_goal_key=None,
    desired_goal_key=None,
    representation_goal_key=None,
    get_action_kwargs=None,
    reset_kwargs=None,
):
    if render_kwargs is None:
        render_kwargs = {}
    if get_action_kwargs is None:
        get_action_kwargs = {}
    observations = [[], []]
    actions = [[], []]
    rewards = [[], []]
    terminals = [[], []]
    agent_infos = [[], []]
    env_infos = [{}, {}]
    next_observations = [[], []]
    paths_length = 0
    agent.reset()
    if reset_kwargs:
        o = env.reset(**reset_kwargs)
    else:
        o = env.reset()
    if render:
        env.render(**render_kwargs)

    def step_agent(env, agent, o):
        if observation_key:
            s = o[observation_key]
        g = o[representation_goal_key]
        new_obs = np.hstack((s, g))
        a, agent_info = agent.get_action(new_obs, **get_action_kwargs)
        next_o, r, d, env_info = env.step(a)
        return a, r, d, next_o, agent_info, env_info

    def append_to_buffer(idx, o, a, r, d, agent_info, env_info):
        observations[idx].append(o)
        rewards[idx].append(r)
        terminals[idx].append(d)
        actions[idx].append(a)
        agent_infos[idx].append(agent_info)
        # observations[running_agent].append(next_o)
        if not env_infos[idx]:
            for k, v in env_info.items():
                env_infos[idx][k] = [v]
        else:
            for k, v in env_info.items():
                env_infos[idx][k].append(v)

    agents_position = [o[achieved_goal_key], o[desired_goal_key]]
    while paths_length < max_path_length:
        # agent0 turn
        env.set_state_goal(agents_position[0], agents_position[1])
        o = env.observation(env.get_state())
        if len(observations[0]) > 0:
            next_observations[0].append(o)
        a, r, d, next_o, agent_info, env_info = step_agent(env, agent, o)
        append_to_buffer(0, o, a, r, d, agent_info, env_info)
        agents_position[0] = next_o[achieved_goal_key]
        if render:
            env.render(**render_kwargs)
        paths_length += 1
        if d or paths_length == max_path_length:
            # if the task is done then there is no agent1 action
            # before getting agent0 observation
            next_observations[0].append(next_o)
            # update agent 1 next_obs after agent 0 move
            env.set_state_goal(agents_position[1], agents_position[0])
            o = env.observation(env.get_state())
            if len(observations[1]) > 0:
                next_observations[1].append(o)
                rewards[1][-1] = r
                terminals[1][-1] = d
                for k, v in env_info.items():
                    env_infos[1][k][-1] = v
            break
        # agent1 turn
        # switch position and goal of the environment from agent1 perspective
        # and recompute observation
        env.set_state_goal(agents_position[1], agents_position[0])
        o = env.observation(env.get_state())
        if len(observations[1]) > 0:
            next_observations[1].append(o)
        a, r, d, next_o, agent_info, env_info = step_agent(env, agent, o)
        append_to_buffer(1, o, a, r, d, agent_info, env_info)
        agents_position[1] = next_o[achieved_goal_key]
        if render:
            env.render(**render_kwargs)
        paths_length += 1
        if d or paths_length == max_path_length:
            # update agent 0 next_obs after agent 1 move
            next_observations[1].append(next_o)
            env.set_state_goal(agents_position[0], agents_position[1])
            o = env.observation(env.get_state())
            next_observations[0].append(o)
            rewards[0][-1] = r
            terminals[0][-1] = d
            for k, v in env_info.items():
                env_infos[0][k][-1] = v
            break
    paths = []
    for i in range(2):
        actions[i] = np.array(actions[i])
        if len(actions[i].shape) == 1:
            actions[i] = np.expand_dims(actions[i], 1)
        observations[i] = np.array(observations[i])
        next_observations[i] = np.array(next_observations[i])
        for k, v in env_infos[i].items():
            env_infos[i][k] = np.array(v)
        paths.append(
            dict(
                observations=observations[i],
                actions=actions[i],
                rewards=np.array(rewards[i]).reshape(-1, 1),
                next_observations=next_observations[i],
                terminals=np.array(terminals[i]).reshape(-1, 1),
                agent_infos=agent_infos[i],
                env_infos=env_infos[i],
            )
        )
    # plot_paths(paths)
    return paths


def plot_paths(paths):
    import matplotlib.pyplot as plt

    fig = plt.figure()
    ax = fig.add_subplot(111, aspect="equal")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    for path, color in zip(paths, ["green", "red"]):
        print(path["terminals"][-1], path["rewards"][-1])
        path = [path["observations"][0]] + list(path["next_observations"])
        for i in range(len(path) - 1):
            p = path[i]["achieved_goal"]
            next_p = path[i + 1]["achieved_goal"]
            ax.scatter(p[0], p[1], c=color)
            ax.scatter(next_p[0], next_p[1], c=color)
            ax.plot([p[0], next_p[0]], [p[1], next_p[1]], c=color)
    plt.show()


def rollout(
    env, agent, max_path_length=np.inf, render=False, render_kwargs=None,
):
    """
    The following value for the following keys will be a 2D array, with the
    first dimension corresponding to the time dimension.
     - observations
     - actions
     - rewards
     - next_observations
     - terminals

    The next two elements will be lists of dictionaries, with the index into
    the list being the index into the time
     - agent_infos
     - env_infos
    """
    if render_kwargs is None:
        render_kwargs = {}
    observations = []
    actions = []
    rewards = []
    terminals = []
    agent_infos = []
    env_infos = []
    o = env.reset()
    agent.reset()
    next_o = None
    path_length = 0
    if render:
        env.render(**render_kwargs)
    while path_length < max_path_length:
        a, agent_info = agent.get_action(o)
        next_o, r, d, env_info = env.step(a)
        observations.append(o)
        rewards.append(r)
        terminals.append(d)
        actions.append(a)
        agent_infos.append(agent_info)
        env_infos.append(env_info)
        path_length += 1
        if d:
            break
        o = next_o
        if render:
            env.render(**render_kwargs)

    actions = np.array(actions)
    if len(actions.shape) == 1:
        actions = np.expand_dims(actions, 1)
    observations = np.array(observations)
    if len(observations.shape) == 1:
        observations = np.expand_dims(observations, 1)
        next_o = np.array([next_o])
    next_observations = np.vstack((observations[1:, :], np.expand_dims(next_o, 0)))
    return dict(
        observations=observations,
        actions=actions,
        rewards=np.array(rewards).reshape(-1, 1),
        next_observations=next_observations,
        terminals=np.array(terminals).reshape(-1, 1),
        agent_infos=agent_infos,
        env_infos=np.array(env_infos),
    )
