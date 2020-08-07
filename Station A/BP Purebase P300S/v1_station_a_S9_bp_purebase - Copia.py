from opentrons import protocol_api
import json
import os
import math

# metadata
metadata = {
    'protocolName': 'Version 1 S9 Station A BP Purebase',
    'author': 'Nick <protocols@opentrons.com>',
    'source': 'Custom Protocol Request',
    'apiLevel': '2.3'
}

NUM_SAMPLES = 12
SAMPLE_VOLUME = 200
LYSIS_VOLUME = 160
IEC_VOLUME = 20
TIP_TRACK = False

DEFAULT_ASPIRATE = 100
DEFAULT_DISPENSE = 100

LYSIS_RATE_ASPIRATE = 100
LYSIS_RATE_DISPENSE = 100

def run(ctx: protocol_api.ProtocolContext):
    ctx.comment("Station A protocol for {} BPGenomics samples.".format(NUM_SAMPLES))
    
    # load labware
    tempdeck = ctx.load_module('Temperature Module Gen2', '10')
    # tempdeck.set_temperature(4)
    internal_control = tempdeck.load_labware(
        'opentrons_96_aluminumblock_generic_pcr_strip_200ul',
        'chilled tubeblock for internal control (strip 1)').wells()[0]
    source_racks = [ctx.load_labware('opentrons_24_tuberack_nest_1.5ml_screwcap', slot,
            'source tuberack ' + str(i+1))
        for i, slot in enumerate(['2', '3', '5', '6'])
    ]
    dest_plate = ctx.load_labware(
        'nest_96_wellplate_2ml_deep', '1', '96-deepwell sample plate')
    lys_buff = ctx.load_labware(
        'opentrons_6_tuberack_falcon_50ml_conical', '4',
        '50ml tuberack for lysis buffer + PK (tube A1)').wells()[0]
    tipracks300 = [ctx.load_labware('opentrons_96_tiprack_300ul', slot,
                                    '200�l filter tiprack')
                    for slot in ['8', '9', '11']]
    tipracks20 = [ctx.load_labware('opentrons_96_filtertiprack_20ul', '7',
                                   '20�l filter tiprack')]

    # load pipette
    m20 = ctx.load_instrument('p20_multi_gen2', 'left', tip_racks=tipracks20)
    p300 = ctx.load_instrument(
        'p300_single_gen2', 'right', tip_racks=tipracks300)
    p300.flow_rate.aspirate = DEFAULT_ASPIRATE
    p300.flow_rate.dispense = DEFAULT_DISPENSE
    p300.flow_rate.blow_out = 300

    # setup samples
    sources = [
        well for rack in source_racks for well in rack.wells()][:NUM_SAMPLES]
    dests_single = dest_plate.wells()[:NUM_SAMPLES]
    dests_multi = dest_plate.rows()[0][:math.ceil(NUM_SAMPLES/8)]

    tip_log = {'count': {}}
    folder_path = '/data/A'
    tip_file_path = folder_path + '/tip_log.json'
    if TIP_TRACK and not ctx.is_simulating():
        if os.path.isfile(tip_file_path):
            with open(tip_file_path) as json_file:
                data = json.load(json_file)
                if 'tips300' in data:
                    tip_log['count'][p300] = data['tips300']
                else:
                    tip_log['count'][p300] = 0
                if 'tips20' in data:
                    tip_log['count'][m20] = data['tips20']
                else:
                    tip_log['count'][m20] = 0
    else:
        tip_log['count'] = {p300: 0, m20: 0}

    tip_log['tips'] = {
        p300: [tip for rack in tipracks300 for tip in rack.wells()],
        m20: [tip for rack in tipracks20 for tip in rack.rows()[0]]
    }
    tip_log['max'] = {
        pip: len(tip_log['tips'][pip])
        for pip in [p300, m20]
    }

    def pick_up(pip):
        nonlocal tip_log
        if tip_log['count'][pip] == tip_log['max'][pip]:
            ctx.pause('Replace ' + str(pip.max_volume) + '�l tipracks before \
resuming.')
            pip.reset_tipracks()
            tip_log['count'][pip] = 0
        pip.pick_up_tip(tip_log['tips'][pip][tip_log['count'][pip]])
        tip_log['count'][pip] += 1

    lysis_total_vol = LYSIS_VOLUME * NUM_SAMPLES

    ctx.comment("Lysis buffer expected volume: {} mL".format(lysis_total_vol/1000))
    
    radius = (lys_buff.diameter)/2
    heights = {lys_buff: lysis_total_vol/(math.pi*(radius**2))}
    ctx.comment("Lysis buffer expected initial height: {:.2f} mm".format(heights[lys_buff]))
    min_h = 5

    def h_track(tube, vol, context):
        nonlocal heights
        dh = vol/(math.pi*(radius**2))
        if heights[tube] - dh > min_h:
            heights[tube] = heights[tube] - dh
        else:
            heights[tube] = min_h
        context.comment("Going {} mm deep".format(heights[tube]))
        return tube.bottom(heights[tube])

    # transfer sample
    for s, d in zip(sources, dests_single):    
        pick_up(p300)
        
        p300.move_to(s.top(10))
        
        ctx.max_speeds['A'] = 20
        
        p300.mix(5, 150, s.bottom(8))
        p300.aspirate(SAMPLE_VOLUME, s.bottom(8))
        p300.air_gap(20)
        
        ctx.max_speeds['A'] = None 
        
        p300.dispense(20, d.top(-2))
        p300.dispense(SAMPLE_VOLUME, d.bottom(5))
        p300.air_gap(20)
        
        #p300.transfer(SAMPLE_VOLUME, s.bottom(8), d.bottom(5), air_gap=20,
        #               new_tip='never')          
        #p300.air_gap(20)
        
        p300.drop_tip()

    # transfer lysis buffer + proteinase K and mix
    p300.flow_rate.aspirate = LYSIS_RATE_ASPIRATE
    p300.flow_rate.dispense = LYSIS_RATE_DISPENSE
    for s, d in zip(sources, dests_single):
        pick_up(p300)
        p300.transfer(LYSIS_VOLUME, h_track(lys_buff, LYSIS_VOLUME, ctx), d.bottom(5), air_gap=20,
                       mix_after=(10, 100), new_tip='never')
        p300.air_gap(20)
        p300.drop_tip()

    ctx.pause('Incubate sample plate (slot 4) at 55-57�C for 20 minutes. \
Return to slot 4 when complete.')

    # transfer internal control
    for d in dests_multi:
        pick_up(m20)
        m20.transfer(IEC_VOLUME, internal_control, d.top(),
                     new_tip='never')
        #m20.transfer(IEC_VOLUME, internal_control, d.top(), air_gap=5,
        #             new_tip='never')
        m20.mix(5, 20, d.bottom(2))
        m20.air_gap(5)
        m20.drop_tip()

    ctx.comment('Move deepwell plate (slot 4) to Station B for RNA \
extraction.')

    # track final used tip
    if not ctx.is_simulating():
        if not os.path.isdir(folder_path):
            os.mkdir(folder_path)
        data = {
            'tips300': tip_log['count'][p300],
            'tips20': tip_log['count'][m20]
        }
        with open(tip_file_path, 'w') as outfile:
            json.dump(data, outfile)
    