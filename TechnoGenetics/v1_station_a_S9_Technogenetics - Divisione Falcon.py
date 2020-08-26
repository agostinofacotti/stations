from opentrons import protocol_api
import json
import os
import math

# metadata
metadata = {
    'protocolName': 'Version 1 Station A Technogenetics',
    'author': 'Marco & Giada',
    'source': 'Custom Protocol Request',
    'apiLevel': '2.3'
}

NUM_SAMPLES = 8
SAMPLE_VOLUME = 200
LYSIS_VOLUME = 400
PK_VOLUME = 30
BEADS_VOLUME = 10
TIP_TRACK = False

DEFAULT_ASPIRATE = 100
DEFAULT_DISPENSE = 100

LYSIS_RATE_ASPIRATE = 100
LYSIS_RATE_DISPENSE = 100

def run(ctx: protocol_api.ProtocolContext):
    ctx.comment("Station A Technogenetics protocol for {} COPAN 330C samples.".format(NUM_SAMPLES))
    # load labware
    source_racks = [ctx.load_labware('copan_15_tuberack_14000ul', slot,
			'source tuberack ' + str(i+1))
        for i, slot in enumerate(['2', '3', '5', '6'])
    ]
    dest_plate = ctx.load_labware(
        'nest_96_wellplate_2ml_deep', '1', '96-deepwell sample plate')
    tempdeck = ctx.load_module('Temperature Module Gen2', '10')
    # tempdeck.set_temperature(4)
    
    strips_block = tempdeck.load_labware(
       'opentrons_96_aluminumblock_generic_pcr_strip_200ul',
       'chilled tubeblock for proteinase K (strip 1) and beads (strip 2)')
    prot_K, beads = strips_block.rows()[0][:2]
    
    lys_buff = ctx.load_labware(
        'opentrons_6_tuberack_falcon_50ml_conical', '4',
        '50ml tuberack for lysis buffer + PK (tube A1)').wells()[0]
    tipracks1000 = [ctx.load_labware('opentrons_96_filtertiprack_1000ul', slot,
                                     '1000µl filter tiprack')
                    for slot in ['8', '9', '11']]
    tipracks20 = [ctx.load_labware('opentrons_96_filtertiprack_20ul', '7',
                                   '20µl filter tiprack')]

    # load pipette
    m20 = ctx.load_instrument('p20_multi_gen2', 'left', tip_racks=tipracks20)
    p1000 = ctx.load_instrument(
        'p1000_single_gen2', 'right', tip_racks=tipracks1000)
    p1000.flow_rate.aspirate = DEFAULT_ASPIRATE
    p1000.flow_rate.dispense = DEFAULT_DISPENSE
    p1000.flow_rate.blow_out = 300

    # setup samples
    # we try to allocate the maximum number of samples available in racks (e.g. 15*number of racks)
    # and after we will ask the user to replace the samples to reach NUM_SAMPLES
    # if number of samples is bigger than samples in racks.
    sources = [
        well for rack in source_racks for well in rack.wells()][:NUM_SAMPLES]
    max_sample_per_set = len(sources)
    set_of_samples = math.ceil(NUM_SAMPLES/max_sample_per_set)
   

    # setup destinations
    dests_single = dest_plate.wells()[:NUM_SAMPLES]
    dests_multi = dest_plate.rows()[0][:math.ceil(NUM_SAMPLES/8)]

    tip_log = {'count': {}}
    folder_path = '/data/A'
    tip_file_path = folder_path + '/tip_log.json'
    if TIP_TRACK and not ctx.is_simulating():
        if os.path.isfile(tip_file_path):
            with open(tip_file_path) as json_file:
                data = json.load(json_file)
                if 'tips1000' in data:
                    tip_log['count'][p1000] = data['tips1000']
                else:
                    tip_log['count'][p1000] = 0
                if 'tips20' in data:
                    tip_log['count'][m20] = data['tips20']
                else:
                    tip_log['count'][m20] = 0
    else:
        tip_log['count'] = {p1000: 0, m20: 0}

    tip_log['tips'] = {
        p1000: [tip for rack in tipracks1000 for tip in rack.wells()],
        m20: [tip for rack in tipracks20 for tip in rack.rows()[0]]
    }
    tip_log['max'] = {
        pip: len(tip_log['tips'][pip])
        for pip in [p1000, m20]
    }

    def pick_up(pip):
        nonlocal tip_log
        if tip_log['count'][pip] == tip_log['max'][pip]:
            ctx.pause('Replace ' + str(pip.max_volume) + 'µl tipracks before \
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
        
    
    # transfer proteinase K
    for idx, d in enumerate(dests_multi):        
        pick_up(m20)
        # transferring proteinase K
        # no air gap to use 1 transfer only avoiding drop during multiple transfers.
        m20.transfer(PK_VOLUME, prot_K, d.bottom(2),
                     new_tip='never')
        m20.air_gap(5)
        m20.drop_tip()
    
    # transfer sample
    done_samples = 0
    refill_of_samples = set_of_samples - 1  # the first set is already filled before start
    ctx.comment("Using {} samples per time".format(max_sample_per_set))
    ctx.comment("We need {} samples refill.".format(refill_of_samples))
    
    for i in range(set_of_samples):
        # setup samples
        remaining_samples = NUM_SAMPLES - done_samples
        ctx.comment("Remaining {} samples".format(remaining_samples))
        
        set_of_sources = sources[:remaining_samples]    # just eventually pick the remaining samples if less than full rack
        destinations = dests_single[done_samples:(done_samples + len(sources))]
  
        ctx.comment("Transferring {} samples".format(len(sources)))
        
        for s, d in zip(sources, destinations):
            pick_up(p1000)
            p1000.mix(5, 150, s.bottom(6))
            p1000.transfer(SAMPLE_VOLUME, s.bottom(6), d.bottom(5), air_gap=100,
                                                    new_tip='never')
            p1000.air_gap(100)
            p1000.drop_tip()

        done_samples = done_samples + len(sources)
        ctx.comment("Done {} samples".format(done_samples))

        if i < (refill_of_samples):
            ctx.pause("Please refill samples")
    
    
    # transfer lysis buffer
    p1000.flow_rate.aspirate = LYSIS_RATE_ASPIRATE
    p1000.flow_rate.dispense = LYSIS_RATE_DISPENSE
    for s, d in zip(sources, dests_single):
        pick_up(p1000)
        p1000.transfer(LYSIS_VOLUME, h_track(lys_buff, LYSIS_VOLUME, ctx), d.bottom(5), air_gap=100,
                       mix_after=(10, 250), new_tip='never')
        p1000.air_gap(100)
        p1000.drop_tip()
    
    ctx.pause("Move deepwell plate to the incubator for 20 minutes at 55°C")
    
    # transfer beads
    for idx, d in enumerate(dests_multi):
        pick_up(m20)
        # transferring beads
        # no air gap to use 1 transfer only avoiding drop during multiple transfers.
        m20.transfer(BEADS_VOLUME, beads, d.bottom(2), air_gap = 5,
                     new_tip='never')
        m20.mix(5, 20, d.bottom(2))
        m20.air_gap(5)
        m20.drop_tip()

    ctx.comment('Move deepwell plate to Station B for RNA extraction.')

    # track final used tip
    if not ctx.is_simulating():
        if not os.path.isdir(folder_path):
            os.mkdir(folder_path)
        data = {
            'tips1000': tip_log['count'][p1000],
            'tips20': tip_log['count'][m20]
        }
        with open(tip_file_path, 'w') as outfile:
            json.dump(data, outfile)
