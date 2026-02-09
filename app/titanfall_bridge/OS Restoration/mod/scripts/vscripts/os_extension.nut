

global function OS_new
global function PlayOneLinerConversationOnEntWithPriority_custom
global function checkPlayerNameBattery
#if CLIENT
global bool alarmIsPlaying = false
global int alarmDamage = 0
void function OS_new(){
	thread menusTread()
}

bool is_boarded = false
bool once = false
bool music = false
//For when player is in lobbies and browser.
void function menusTread(){
	WaitFrame()
	int noConsoleSpam = 0
	while(IsLobby() && IsMenuLevel()){
		if(noConsoleSpam <= 0 ){
		print("waiting for game")
		noConsoleSpam = 2
	}
		else
		WaitForever()
	}

	thread Os_running()
}



void function Os_running(){
	print("OS is now running")
	while(true){
		if(!IsLobby() && !IsMenuLevel())
		{
			WaitFrame()
		}


		entity player = GetLocalViewPlayer()
	//	print("batteries " + GetClientEntArrayBySignifier( "item_titan_battery" ).len())
		while(IsWatchingReplay())
		{
			WaitFrame()
		}
		if(IsValid(player))
	 	{
		 if((player.IsTitan() == true))
		{

				if(once == false)
				{
					print("boarded..")
					is_boarded = true
					once = true
					print("once is " + once )
					thread battery_radar(player)
					thread damage_alarm(player)
					thread rodeo_checker(player)
				}
				

		}
		else if ((player.GetPetTitan() != null))
		{
			if(is_boarded == true)
			{
				is_boarded = false
				once = false
				music = true
				print("disembarking...")
				if(player.GetPetTitan().GetTitanSoul().IsEjecting() == false)
				{
					//TitanCockpit_PlayDialogDelayed( player, 0.0, "disembark" )
					TitanCockpit_PlayDialog( GetLocalViewPlayer(), "disembark" )
				}
				
			}
			if(music == false)
			{
			//	wait 0.2
			//	thread PlayOneLinerConversationOnEntWithPriority_custom( "music_wilds_16d_embark", player, 1275 )
		//		print("playing music")
			//	thread FadeOutSoundOnEntity(player,"music_wilds_16d_embark",2)
				music = true
			}
			
		}
		else
		{
	//		print("hello peter 3")
			is_boarded = false
			once = false
			music = false
		}
		}
		
//		WaitFrame()
	}
 }

 void function battery_radar(entity player)
 {
	 wait 3
	 if(!IsValid(player))
	 {
		 return
	 }
	 if ( IsWatchingReplay() )
		 return	
	 if ( !IsConnected() ) 
		return
		print("battery radar is now running")
	string conversationName = "batteryNearDisembark"
	string soundAlias = GenerateTitanOSAlias_custom( player, conversationName )
	string conversationName2 = "batteryNearGeneric"
	string soundAlias2 = GenerateTitanOSAlias_custom( player, conversationName2 )
	if(IsValid(player))
	 {
		while(is_boarded)
		{
			if ( IsWatchingReplay() )
			return
			array<entity> batteries = GetClientEntArrayBySignifier( "item_titan_battery" )
			//print("total batteries now is " + batteries.len())
			foreach ( entity battery in batteries )
			{
					if(!IsValid(battery))
					{	
						break
					}
					float dist3d = Length( player.GetOrigin() -  (battery.GetOrigin()))
				//	print ("Bossplayer of the battery is " + battery.GetParent())
					if(battery.GetParent() == null)
					{
						if(dist3d < 500)
						{
							if ( IsWatchingReplay() )
								return	
							string conversationName = "batteryNearDisembark"
							thread PlayOneLinerConversationOnEntWithPriority_custom( soundAlias, player, 275 )
							wait 15
						}
						else if(dist3d < 2600)
						{
							if ( IsWatchingReplay() )
								return
							string conversationName = "batteryNearGeneric"
							thread PlayOneLinerConversationOnEntWithPriority_custom( soundAlias2, player, 275 )
							wait 15
						}
					}
				
			}
			wait 2
		}
	 }
	print("battery radar has ended")
 }
string function GenerateTitanOSAlias_custom( entity player, string aliasSuffix )
{
	//HACK: Temp fix for blocker bug. Fixing correctly next.
	if ( IsSingleplayer() )
	{
		return "diag_gs_titanBt_" + aliasSuffix
	}
	else
	{
		entity titan
		if ( player.IsTitan() )
			titan = player
		else
			titan = player.GetPetTitan()

		Assert( IsValid( titan ) )
		string titanCharacterName = GetTitanCharacterName_custom( titan )
		string primeTitanString = ""

		if ( IsTitanPrimeTitan_custom( titan ) )
			primeTitanString = "_prime"

		string modifiedAlias = "diag_gs_titan" + titanCharacterName + primeTitanString + "_" + aliasSuffix
		
		return modifiedAlias
	}
	unreachable
}
bool function IsTitanPrimeTitan_custom( entity titan )
{
	Assert( titan.IsTitan() )
	string setFile
	if(!IsValid(titan))
	{
		print("null failsafe for prime is working")
		return false
	}
	if ( titan.IsPlayer() )
	{
		setFile = titan.GetPlayerSettings()
	}
	else
	{
		string aiSettingsFile = titan.GetAISettingsName()
		setFile = expect string( Dev_GetAISettingByKeyField_Global( aiSettingsFile, "npc_titan_player_settings" ) )
	}

	return  Dev_GetPlayerSettingByKeyField_Global( setFile, "isPrime" ) == 1

}

string function GetTitanCharacterName_custom( entity titan )
{
	Assert( titan.IsTitan() )

	string setFile
	if(!IsValid(titan))
	{
		print("null failsafe for character name is working")
		return ""
	}
	if ( titan.IsPlayer() )
	{
		setFile = titan.GetPlayerSettings()
	}
	else
	{
		string aiSettingsFile = titan.GetAISettingsName()
		setFile = expect string( Dev_GetAISettingByKeyField_Global( aiSettingsFile, "npc_titan_player_settings" ) )
	}

	return GetTitanCharacterNameFromSetFile( setFile )
}

  void function damage_alarm(entity player)
 {
	 wait 1
	 print("damage alarm has started")
	if(!IsValid(player))
	 {
		 return
	 }
	 if ( IsWatchingReplay() )
		 return	
	 if ( !IsConnected() ) 
		return
	 while(is_boarded)
	{
		if ( IsWatchingReplay() )
			return



		int prevHealth = player.GetHealth()
		string conversationName = "bettyAlarm"
		string soundAlias = GenerateTitanOSAlias_custom( player, conversationName )
		int milliseconds = 0
		//entity weapon = player.GetOffhandWeapon( OFFHAND_EQUIPMENT )
		while(IsValid(player))
		{
			if(prevHealth == player.GetHealth())
			{
				WaitFrame()
			}
			else
			{
				break
			}
			
		}
		if(is_boarded == false)
		{
			print("damage alarm has ended due to auto titan")
			return
		}
		while (milliseconds < 220)
		{
			if ( IsWatchingReplay() )
			{
				return
			}
			if(!IsValid(player))
	 		{
				 return
			}
			int currentHealth = player.GetHealth()
			
			alarmDamage = prevHealth - currentHealth
		//	print("alarmDamage is " + alarmDamage + "in millisecond: " + milliseconds)
			if((prevHealth - currentHealth) > 1999)
			{
				
				if(IsValid(player))
	 			{
					
					if(player != null)
					{
						
			//			thread PlayOneLinerConversationOnEntWithPriority_internal( soundAlias, player, 2 )
						if(player.IsTitan())
						{
						//	thread EmitSoundOnEntity( player , soundAlias )
						//	thread PlayOneLinerConversationOnEntWithPriority_custom( soundAlias, player, 1000)
					//	 if(briefCriticalDamageisPlaying == false)
				//		 {
							
					//		thread EmitSoundOnEntity( player , "diag_gs_titanIon_bettyAlarm" )
							if(IsAlive(player))
							{
								
						//		print("alarm current health is " + currentHealth)
								alarmIsPlaying = true
								thread PlayOneLinerConversationOnEntWithPriority_custom( soundAlias, player, 1000)
								wait 0.6
								alarmIsPlaying = false
								
								
							}
						    
						 //	thread ForcePlayMusic( "diag_gs_titanIon_bettyAlarm" )
						    
			//			 }
							
						//	GetLocalClientPlayer().ClientCommand("playvideo titan_alarm 1 1")
						//	wait 0.6
							break
						}
					}
					
	 			}
				
				
				
			}
			if(IsValid(player))
	 		{
				bool isDoomed = GetDoomedState( player )
				if(isDoomed)
				{
					/*
					if((prevHealth - currentHealth) > 499)
					{
						
						if(IsValid(player))
						{
							
							if(player != null)
							{
								
					//			thread PlayOneLinerConversationOnEntWithPriority_internal( soundAlias, player, 2 )
								if(player.IsTitan())
								{
								//	thread EmitSoundOnEntity( player , soundAlias )
								//	thread PlayOneLinerConversationOnEntWithPriority_custom( soundAlias, player, 1000)
							//	 if(briefCriticalDamageisPlaying == false)
						//		 {
									alarmIsPlaying = true
							//		thread EmitSoundOnEntity( player , "diag_gs_titanIon_bettyAlarm" )
									thread PlayOneLinerConversationOnEntWithPriority_custom( soundAlias, player, 399)
									wait 0.6
									alarmIsPlaying = false
					//			 }
									
								//	GetLocalClientPlayer().ClientCommand("playvideo titan_alarm 1 1")
								//	wait 0.6
									break
								}
							}
							
						}
						
						
						
					}
					*/
					return
				}
			}
			milliseconds = milliseconds + 1
			wait 0.001
		}
		WaitFrame()
		alarmDamage = 0
	}
	print("damage alarm has ended")
 }

 void function rodeo_checker(entity player)
 {
	  wait 1
	 print("rodeo checker has started")
	 string conversationName1 = "hostileLeftHull"
	 string conversationName2 = "repelEnemyRodeo"
	 string conversationName3 = "batteryStolenByPilot"
	 string conversationName4 = "batteryStolenGnrc"
	 string conversationName5 = "repelEnemyRodeoGnrc"
	 string soundAlias_left = GenerateTitanOSAlias_custom( player, conversationName1 )
	 string soundAlias_dead = GenerateTitanOSAlias_custom( player, conversationName2 )
	 string soundAlias_deadgnrc = GenerateTitanOSAlias_custom( player, conversationName5 )
	 string soundAlias_stolen = GenerateTitanOSAlias_custom( player, conversationName3 )
	 string soundAlias_stolengnrc = GenerateTitanOSAlias_custom( player, conversationName4 )
	// thread PlayOneLinerConversationOnEntWithPriority_internal( soundAlias, player, 2 )
	if(!IsValid(player))
	 {
		 return
	 }
	 if ( IsWatchingReplay() )
		 return	
	 if ( !IsConnected() ) 
		return
	bool hostileOnBoard = false
	bool BoardedWithBattery = false
	entity prevrider
	 while(is_boarded)
	{
		if ( IsWatchingReplay() )
			return
		entity rider = GetRodeoPilot( player )
		
		if(rider == null)
		{
			
		//	print("no current rodeo")
			if(hostileOnBoard == true)
			{
			//	print("debug riderz 0")
				if(!IsValid(prevrider))
	 			{
				  break
	 			}
					if(BoardedWithBattery == false)
					{
						
					//	print("debug riderz 1")

						if(!IsValid(prevrider))
	 					{
				//			 print("invalid rider")
						  break
	 					}
						wait 0.2
						bool currentlyWithBattery = checkPlayerNameBattery( prevrider.GetPlayerName())
					//	print("the battery status of " + prevrider.GetPlayerName() + "is " + checkPlayerNameBattery( prevrider.GetPlayerName()) )
						if(checkPlayerNameBattery( prevrider.GetPlayerName()))
						{
						//	print("debug riderz 2")
							int random = RandomInt( 2 )
							if(random == 0)
							{
								thread PlayOneLinerConversationOnEntWithPriority_custom( soundAlias_stolengnrc, player, 2001 )
							}
							else
							{
								thread PlayOneLinerConversationOnEntWithPriority_custom( soundAlias_stolen, player, 2001 )
							}
							
						}
						else
						{
							wait 0.3
							if ( IsAlive( prevrider ) )
							{
						//		print("debug riderz 3")
								thread PlayOneLinerConversationOnEntWithPriority_custom( soundAlias_left, player, 2001 )
							}
							else
							{
						//		print("debug riderz 4")
								int random = RandomInt( 2 )
								if(random == 0)
								{
									thread PlayOneLinerConversationOnEntWithPriority_custom( soundAlias_dead, player, 2001 )
								}
								else
								{
									thread PlayOneLinerConversationOnEntWithPriority_custom( soundAlias_deadgnrc, player, 2001 )
								}
								
							}
						}
						
					}
					else
					{
			//			print("debug riderz 7")
						if(!IsValid(prevrider))
						{
							print("invalid rider")
							break
						}
						wait 0.3
						if ( IsAlive( prevrider ) )
						{
				//			print("debug riderz 5")
							thread PlayOneLinerConversationOnEntWithPriority_custom( soundAlias_left, player, 2001 )
						}
						else
						{
				//			print("debug riderz 6")
							int random = RandomInt( 2 )
							if(random == 0)
							{
								thread PlayOneLinerConversationOnEntWithPriority_custom( soundAlias_dead, player, 2001 )
							}
							else
							{
								thread PlayOneLinerConversationOnEntWithPriority_custom( soundAlias_deadgnrc, player, 2001 )
							}
						}
					}
			}
			hostileOnBoard = false
			prevrider = null
			BoardedWithBattery = false

		}
		else if(rider != null)
		{
			if(IsValid(rider))
	 		{
				if(rider.GetTeam() != player.GetTeam())
				{
					if(hostileOnBoard == false)
					{
						print("debug riderz 7")
						BoardedWithBattery = checkPlayerNameBattery( rider.GetPlayerName())

						print("the current rider is " + rider.GetPlayerName() + " with battery? " + checkPlayerNameBattery( rider.GetPlayerName() ))
						prevrider = rider
					}
					hostileOnBoard = true
				}
			}	
		}
		WaitFrame()
	}
	print("rodeo checker has ended")
 }
bool function checkPlayerNameBattery(string name)
{
	array<entity> batteries = GetClientEntArrayBySignifier( "item_titan_battery" )
	entity player_found
	foreach ( player in GetPlayerArray() )
	{
		
		if(name == player.GetPlayerName())
		{
			if(!IsValid(player))
			{
				return false
			}
			player_found = player
		}
	}
	if(!IsValid(player_found))
	{
		return false
	}
	foreach ( battery in batteries )
	{
		if(battery.GetParent() != null)
		{
			if(battery.GetParent().GetPlayerName() == player_found.GetPlayerName())
			{
				return true
			}
		}
	}
	
	return false
}
void function PlayOneLinerConversationOnEntWithPriority_custom(string soundAlias, entity ent, int priority )
{
	bool printDebug = GetDialogueDebugLevel() > 0
//	if ( printDebug )
//		printt( "PlayOneLinerConversationOnEntWithPriority, ConversationName: " + conversationName )

	if ( AbortConversationDueToPriority( priority ) )
	{
	//	if ( printDebug )
	//		printt( "Aborting conversation: " + conversationName + " due to higher priority conversation going on" )
		print(soundAlias + "aborted due to priority")
		return
	}

	CancelConversation( ent )
	
//	SetConversationLastPlayedTime( conversationName, Time() )

	thread PlayOneLinerConversationOnEntWithPriority_internal( soundAlias, ent, priority ) //Only thread this off once we've done the priority check since threading is expensive

}
/*
void function battery_checker(entity player)
{
	while(player.IsTitan())
	{
		array<ArrayDistanceEntry> allResults = ArrayDistanceResults( file.batteries, player.GetOrigin() )
			allResults.sort( DistanceCompareClosest )
			if(allResults.len() == 0)
			{
				print("no batteries found")
			}
			else
			{
				for ( int i=0; i<allResults.len(); i++ )
				{
					print("nearest battery is in " + allResults [o])
				}
			}
			
	}
	

}
*/

#endif
