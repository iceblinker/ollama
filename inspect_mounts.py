import subprocess
import json

try:
    result = subprocess.run(['docker', 'inspect', 'vixsrc-addon'], capture_output=True, text=True)
    data = json.loads(result.stdout)
    for container in data:
        print(f"Container: {container['Name']}")
        for mount in container['Mounts']:
            dst = mount.get('Destination', mount.get('Target', 'N/A'))
            print(f"MOUNT: {dst}")
except Exception as e:
    print(e)
