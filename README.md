# Install
```yaml
homeassistant:
  packages:
    config_generator: !include components/config_generator/root.yaml
```

# Usage

## Instances
Data source for generating templates. The keys of tmaps can be used as variables.
## Templates
Templates which generated for all of the map listed in instances section. Can be filtered by *where* statement. The *target* is the folder where the file will be generated with the specified *name*. Variables can be used ffrom the instances map with **<>**: **<room>**. These can be used in lowercase: **<_room_>**.
## Summaries
Each summary template contains the followings:
- where: filter instances included in a summary
- group_by: key used for grouping instances
- each: templates to run for each group. Special variables: **<group>** the name of the group and **<instances>** a jinja template array with the contained instances
- final: templates to run once in a summary. Special variable:  **<groups>** a jinja template array with the contained groups

## Example 
```yaml
instances:
  - name: Window
    room: kitchen
    topic: contact/window
    type: contact
    
  - name: Motion
    room: kitchen
    topic: motion
    type: motion

  - name: Wall Switch
    room: office
    topic: wall_switch
    type: switch_single
    energy_meter: true
templates:
  - target: ../switch
    name: '<<_room_>>'
    where:
      type: switch_single
    template: 
    - platform: mqtt
        name: <<room>> <<name>>
        state_topic: '<<global.mqtt_prefix>>/<<room>>/<<topic>>'
        command_topic: '<<global.mqtt_prefix>>/<<room>>/<<topic>>/set'
        value_template: '{{ value_json.state }}'
        state_on: 'ON'
        state_off: 'OFF'
        payload_on: '{ "state": "ON" }'
        payload_off: '{ "state": "OFF" }'
        json_attributes_topic: '<<global.mqtt_prefix>>/<<room>>/<<topic>>'
        json_attributes_template: >
        {
            {% if "illuminance" in value_json %}
                "illuminance": {{value_json.illuminance}},
            {% endif %}
            {% if "battery" in value_json %}
                "battery": {{value_json.battery}},
            {% endif %}
            {% if "power" in value_json %}
                "power": {{value_json.power}},
            {% endif %}
            "last_seen": {{value_json.last_seen}},
            "linkquality": {{value_json.linkquality}} 
        }  
summaries:
  - where: 
      energy_meter: true
    group_by: room
    each:
    - target: ../sensor
        name: power.group.<<_group_>>
        template:
        - platform: template
            sensors:
            <<_group_>>_power:
                friendly_name: '<<group>> power'
                value_template: >
                    {% set array = <<instances>> %}
                    {% set sum = namespace(states=[]) %}
                    {% for i in array %}
                    {% set sum.states = sum.states + [states('sensor.<<_group_>>_' + i["name"].lower().replace(' ', '_') + '_power')|float] %}
                    {% endfor %}
                    {{ sum.states | sum | round(2) }}
                unit_of_measurement: w
    - target: ../sensor
        name: <<_group_>>
        template:
        - platform: integration
            source: sensor.<<_group_>>_power
            name: <<group>> Consumption
            round: 2
            unit: w
            unit_prefix: k
    - target: ../utility_meter
        name: <<_group_>>
        template:
        <<_group_>>_consumption_monthly:
            source: sensor.<<_group_>>_consumption
            cycle: monthly
        <<_group_>>_consumption_daily:
            source: sensor.<<_group_>>_consumption
            cycle: daily
    final:
    - target: ../sensor
        name: power.sum.home
        template:
        - platform: template
            sensors:
            home_power:
                friendly_name: 'Home power'
                value_template: >
                    {% set array = <<groups>> %}
                    {% set sum = namespace(states=[]) %}
                    {% for i in array %}
                    {% set sum.states = sum.states + [states('sensor.' + i["group"].lower().replace(' ', '_') + '_power')|float] %}
                    {% endfor %}
                    {{ sum.states | sum | round(2) }}
                unit_of_measurement: w
    - target: ../sensor
        name: Home.power
        template:
        - platform: integration
            source: sensor.home_power
            name: Home Consumption
            round: 2
            unit: w
            unit_prefix: k
    - target: ../utility_meter
        name: power.sum.home
        template:
        home_consumption_monthly:
            source: sensor.home_consumption
            cycle: monthly
        home_consumption_daily:
            source: sensor.home_consumption
            cycle: daily
```