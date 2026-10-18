import oci

config = oci.config.from_file('~/.oci/config', 'DEFAULT')
oci.config.validate_config(config)
print("config ok")
