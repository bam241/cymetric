import pandas as pd
import numpy as np

try:
    from graphviz import Digraph
    HAVE_GRAPHVIZ = True
except ImportError:
    HAVE_GRAPHVIZ = False

try:
    from pyne import data
    import pyne.enrichment as enr
    from pyne import nucname
    HAVE_PYNE = True
except ImportError:
    HAVE_PYNE = False


import cymetric as cym
from cymetric import tools
from cymetric.tools import format_nuc
from cymetric.tools import reduce
from cymetric.tools import merge
from cymetric.tools import add_missing_time_step


def get_transaction_df(evaler, senders=(), receivers=(), commodities=()):
    """
    Filter the Transaction Data Frame on specific sending facility and
    receving facility.

    Parameters
    ----------
    evaler : evaler
    senders :  of the sending facility
    receivers :  of the receiving facility
    commodities :  of the commodity exchanged
    """

    # initiate evaluation
    trans = evaler.eval('Transactions')
    agents = evaler.eval('AgentEntry')

    rec_agent = agents.rename(index=str, columns={'AgentId': 'ReceiverId'})
    if len(receivers) != 0:
        rec_agent = rec_agent[rec_agent['Prototype'].isin(receivers)]

    send_agent = agents.rename(index=str, columns={'AgentId': 'SenderId'})
    if len(senders) != 0:
        send_agent = send_agent[send_agent['Prototype'].isin(senders)]

    # check if sender and receiver exist
    if rec_agent.empty or send_agent.empty:
        return None

    # Clean Transation PDF
    rdc_ = []
    rdc_.append(['ReceiverId', rec_agent['ReceiverId'].tolist()])
    rdc_.append(['SenderId', send_agent['SenderId'].tolist()])
    if len(commodities) != 0:
        rdc_.append(['Commodity', commodities])

    trans = reduce(trans, rdc_)

    # Merge Sender to Transaction PDF
    base_col = ['SimId', 'SenderId']
    added_col = base_col + ['Prototype']
    trans = merge(trans, base_col, send_agent, added_col)
    trans = trans.rename(index=str, columns={
                         'Prototype': 'SenderPrototype'})

    # Merge Receiver to Transaction PDF
    base_col = ['SimId', 'ReceiverId']
    added_col = base_col + ['Prototype']
    trans = merge(trans, base_col, rec_agent, added_col)
    trans = trans.rename(index=str, columns={
                         'Prototype': 'ReceiverPrototype'})

    return trans


def get_transaction_nuc_df(evaler, senders=(), receivers=(), commodities=(), nucs=()):
    """
    Filter the Transaction Data Frame, which include nuclide composition, on specific sending facility and
    receving facility. Applying nuclides selection when required.

    Parameters
    ----------
    evaler : evaler
    senders :  of the sending facility
    receivers :  of the receiving facility
    commodities :  of the commodity exchanged
    nucs :  of nuclide to select.
    """

    compo = evaler.eval('Materials')

    df = get_transaction_df(evaler, senders, receivers, commodities)

    if len(nucs) != 0:
        nucs = format_nuc(nucs)
        compo = reduce(compo, [['NucId', nucs]])

    base_col = ['SimId', 'ResourceId']
    added_col = base_col + ['NucId', 'Mass']
    df = merge(df, base_col, compo, added_col)

    return df


def get_transaction_activity_df(evaler, senders=(), receivers=(), commodities=(), nucs=()):
    """
    Return the transation df, with the activities. Applying nuclides selection when required.

    Parameters
    ----------
    evaler : evaler
    senders :  of the sending facility
    receivers :  of the receiving facility
    commodities :  of the commodity exchanged
    nucs :  of nuclide to select.
    """

    df = get_transaction_df(evaler, senders, receivers, commodities)

    if len(nucs) != 0:
        nucs = format_nuc(nucs)

    compo = evaler.eval('Activity')
    compo = reduce(compo, [['NucId', nucs]])

    base_col = ['SimId', 'ResourceId']
    added_col = base_col + ['NucId', 'Activity']
    df = merge(df, base_col, compo, added_col)

    return df


def get_transaction_decayheat_df(evaler, senders=(), receivers=(), commodities=(), nucs=()):
    """
    Return the transation df, with the decayheat. Applying nuclides selection when required.

    Parameters
    ----------
    evaler : evaler
    senders :  of the sending facility
    receivers :  of the receiving facility
    commodities :  of the commodity exchanged
    nucs :  of nuclide to select.
    """

    df = get_transaction_df(evaler, senders, receivers, commodities)

    if len(nucs) != 0:
        nucs = format_nuc(nucs)

    compo = evaler.eval('DecayHeat')
    compo = reduce(compo, [['NucId', nucs]])

    base_col = ['SimId', 'ResourceId']
    added_col = base_col + ['NucId', 'DecayHeat']
    df = merge(df, base_col, compo, added_col)

    return df


def get_inventory_df(evaler, facilities=(), nucs=()):
    """
    Shape the reduced inventory Data Frame. Applying nuclides/facilities selection when required.

    Parameters
    ----------
    evaler : evaler
    facilities :  of the facility
    nucs :  of nuclide to select.
    """

    # Get inventory table
    df = evaler.eval('ExplicitInventory')
    agents = evaler.eval('AgentEntry')

    rdc_ = []  # because we want to get rid of the nuclide asap
    if len(nucs) != 0:
        nucs = format_nuc(nucs)
        rdc_.append(['NucId', nucs])

    if len(facilities) != 0:
        agents = agents[agents['Prototype'].isin(facilities)]
        rdc_.append(['AgentId', agents['AgentId'].tolist()])
    else:
        wng_msg = "no faciity provided"
        warnings.warn(wng_msg, UserWarning)
    df = reduce(df, rdc_)

    base_col = ['SimId', 'AgentId']
    added_col = base_col + ['Prototype']
    df = merge(df, base_col, agents, added_col)

    return df


def get_inventory_activity_df(evaler, facilities=(), nucs=()):
    """
    Get a simple time series of the activity of the inventory in the selcted
    facilities. Applying nuclides selection when required.

    Parameters
    ----------
    evaler : evaler
    facilities :  of the facility
    nucs :  of nuclide to select.
    """

    if len(nucs) != 0:
        nucs = format_nuc(nucs)

    df = get_inventory_df(evaler, facilities, nucs)
    for i, row in df.iterrows():
        val = 1000 * data.N_A * row['Quantity'] * \
            data.decay_const(int(row['NucId']))
        df.set_value(i, 'Activity', val)

    return df


def get_inventory_decayheat_df(evaler, facilities=(), nucs=()):
    """
    Get a Inventory PDF including the decay heat of the inventory in the selected
    facilities. Applying nuclides selection when required.

    Parameters
    ----------
    evaler : evaler
    facilities :  of the facility
    nucs :  of nuclide to select.
    """

    if len(nucs) != 0:
        nucs = format_nuc(nucs)

    df = get_inventory_activity_df(evaler, facilities, nucs)
    for i, row in df.iterrows():
        val = data.MeV_per_MJ * \
            row['Activity'] * data.q_val(int(row['NucId']))
        df.set_value(i, 'DecayHeat', val)

    return df