#!/usr/bin/perl
###############################################################################
#                                                                             #
# VLAN Management for IPFire                                                  #
# Copyright (C) 2019 Florian Bührle <erdlof@protonmail.com>                   #
#                                                                             #
# This program is free software: you can redistribute it and/or modify        #
# it under the terms of the GNU General Public License as published by        #
# the Free Software Foundation, either version 3 of the License, or           #
# (at your option) any later version.                                         #
#                                                                             #
# This program is distributed in the hope that it will be useful,             #
# but WITHOUT ANY WARRANTY; without even the implied warranty of              #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the               #
# GNU General Public License for more details.                                #
#                                                                             #
# You should have received a copy of the GNU General Public License           #
# along with this program.  If not, see <http://www.gnu.org/licenses/>.       #
#                                                                             #
###############################################################################

use strict;
#use warnings;
#use CGI::Carp 'fatalsToBrowser';
use Scalar::Util qw(looks_like_number);

require '/var/ipfire/general-functions.pl';
require "${General::swroot}/lang.pl";
require "${General::swroot}/header.pl";

# Define all zones we will check for NIC assignment
my @zones = ("green", "red", "orange", "blue");

# Get all physical NICs
my @nics = `ls /sys/class/net/`;
chomp @nics;

@nics = (sub {
	my @temp;

	foreach (@nics) {
		if (-e "/sys/class/net/$_/device") { # Indicates that this NIC is physical
			push(@temp, $_);
		}
	}

	return @temp;
})->();

# Read network settings
sub get_config_data($) # Get values from the ethernet settings file
{
	my @netconf = split ("\n", &General::read_file_utf8("${General::swroot}/ethernet/settings"));
	chomp @netconf;

	foreach ( @netconf ) {
		my @line = split("=", $_);

		if (@line[0] eq @_[0]) {
			return @line[1];
		}
	}

	return
}

# Write network settings
sub write_config_data($$) {
	my ($key, $val) = (@_);
	my @netconf = split ("\n", &General::read_file_utf8("${General::swroot}/vlan/settings"));
	chomp @netconf;

	open my $fh, '>', "${General::swroot}/vlan/settings" or die "$!";
	
	my $found = 0;
	foreach (@netconf) {
		my @line = split("=", $_);

		if (@line[0] eq $key) {
			print $fh "$key=$val\n";
			$found = 1;
		} else {
			print $fh "$_\n";
		}
	}

	if (! $found) {
		print $fh "$key=$val\n";
	}

	close $fh;
}

### READ CGI INPUT ###
my %cgiparams=();

&Header::getcgihash(\%cgiparams);

&Header::showhttpheaders();

if ($cgiparams{"ACTION"} eq "Apply") {
	foreach (@zones) {
		my $uc = uc $_;
		my $access_string = "";

		foreach (@nics) {
			if (my $access = $cgiparams{"ACCESS $uc $_"}) {
				if ($access eq "NATIVE") {
					$access_string = "$access_string$_ ";
				} elsif ($access eq "VLAN") {
					my $tag = $cgiparams{"TAG $uc $_"};

					if (! looks_like_number($tag)) {
						next;
					}
					if ($tag < 1 || $tag > 4095) {
						next;
					}

					$access_string = "$access_string$_.$tag ";
				}
			}
		}

		write_config_data("${uc}_INTERFACES", $access_string);
	}

	my $refresh = "<meta http-equiv='refresh' content='2; URL=/cgi-bin/vlans.cgi' />";

	&Header::openpage("VLAN reload", 0, $refresh);

	&Header::openbigbox('100%', 'center');
	print <<END
<div align='center'>
<table width='100%' bgcolor='#ffffff'>
<tr><td align='center'>
<br /><br /><img src='/images/IPFire.png' /><br /><br /><br />
</td></tr>
</table>
<br />
<font size='6'>Reloading network settings</font>
</div>
END
	;

	&Header::closebigbox();
	&Header::closepage();

	system('/usr/bin/touch', "${General::swroot}/vlan/restart"); # TODO: Call helper program
	
} else {

	&Header::openpage("VLAN Configuration", 1, '');

	&Header::openbigbox('100%', 'center');

	&Header::openbox('100%', 'left', "NIC Assignment");

	### START OF TABLE ###

	# Style in body is a bit hacky, but works
	print <<END
	<style>
	table {
		width: 100%;
	}

	tr {
		height: 3.5em;
	}

	td:first-child {
		width: 1px;
	}

	td {
		padding: 5px;
		padding-left: 10px;
		padding-right: 10px;
		border: 0.5px solid black;
	}

	table {
		border-collapse: collapse;
	}

	td.h {
		background-color: grey;
		color: white;
		font-weight: 800;
	}

	td.green {
		background-color: green;
	}

	td.red {
		background-color: red;
	}

	td.blue {
		background-color: blue;
	}

	td.orange {
		background-color: orange;
	}

	td.topleft {
		background-color: white;
		border-top-style: none;
		border-left-style: none;
	}

	td.disabled {
		background-color: #cccccc;
	}

	td.textcenter {
		text-align: center;
	}

	#submit-container {
		display: flex;
		width: 100%;
		justify-content: space-between;
		padding-top: 20px;
		text-align: left;
	}

	#submit-container.input {
		margin-left: auto;
	}

	</style>
	<form method='post' enctype='multipart/form-data'>
		<table>
			<tr>
			<td class="h topleft" /td>
END
;

	foreach (@nics) {
		print "<td class='h textcenter'>$_</td>";
	}

	print "</tr>";

	# Iterate through all zones and display the runtime config.
	# We could also read all from the settings file but this
	# approach allows for more flexibility.

	foreach (@zones) {
		print "<tr>";
		my $uc = uc $_;

		# Get the corresponding 
		my $bridge_name = get_config_data("${uc}_DEV");

		if ((! -d "/sys/class/net/$bridge_name") || ($bridge_name eq "")) { # If the zone is not activated, color it light grey
			print "<td class='h disabled'>$uc</td>";

			foreach (@nics) {
				print "<td class='disabled'/>";
			}

			print "</tr>";

			next;
		}

		print "<td class='h $_'>$uc ($bridge_name)</td>";

		foreach (@nics) {
			my @vlans = `ls /sys/class/net/ | grep $_`;
			chomp @vlans;

			my %selected=();
			my $vlan_id;

			foreach (@vlans) {
				if (-d "/sys/class/net/$_/upper_$bridge_name") {
					my @int = split('\.', $_);
					
					if (@int == 1) {
						$selected{"NATIVE"} = "selected";
					} else {
						$selected{"VLAN"} = "selected";
						$vlan_id = @int[1];
					}

					last;
				}
			}

			$selected{"NONE"} = ($selected{"NATIVE"} eq "") && ($selected{"VLAN"} eq "") ? "selected" : "";

			my $field_disabled = ($selected{"VLAN"} eq "") ? "disabled" : "";

			print <<END
				<td class="textcenter">
					<select name="ACCESS $uc $_" onchange="document.getElementById('TAG $uc $_').disabled = (this.value === 'VLAN' ? false : true)">
						<option value="NATIVE" $selected{"NATIVE"}>Native</option>
						<option value="VLAN" $selected{"VLAN"}>VLAN</option>
						<option value="NONE" $selected{"NONE"}>None</option>
					</select>
					<input type="number" id="TAG $uc $_" name="TAG $uc $_" min="1" max="4095" value="$vlan_id" $field_disabled>
				</td>
END
;
		}

		print "</tr>";
	}

	print <<END
	</table>
		<div id="submit-container">
			<font color="red">Warning: Incorrect configuration may render this web interface unreachable!</font>
			<input type="submit" name="ACTION" value="Apply">
		</div>
	</form>
END
;

	&Header::closebox();

	&Header::closebigbox();

	&Header::closepage();

}
